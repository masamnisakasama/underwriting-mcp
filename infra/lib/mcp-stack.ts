import * as cdk from "aws-cdk-lib";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ecsPatterns from "aws-cdk-lib/aws-ecs-patterns";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as logs from "aws-cdk-lib/aws-logs";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as route53Targets from "aws-cdk-lib/aws-route53-targets";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import * as sfn from "aws-cdk-lib/aws-stepfunctions";
import * as wafv2 from "aws-cdk-lib/aws-wafv2";
import { Construct } from "constructs";

export interface McpStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
  bucket: s3.IBucket;
  table: dynamodb.ITable;
  stateMachine: sfn.IStateMachine;
}

export class McpStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: McpStackProps) {
    super(scope, id, props);

    const cluster = new ecs.Cluster(this, "Cluster", { vpc: props.vpc });
    const deploymentMode =
      (this.node.tryGetContext("deploymentMode") as string | undefined) ?? "private";
    const lowCostDemo = deploymentMode === "demo-low-cost";
    const enableWafContext = this.node.tryGetContext("enableWaf") as string | undefined;
    const enableWaf =
      enableWafContext === undefined ? !lowCostDemo : enableWafContext === "true";
    const configuredSecretArn = this.node.tryGetContext("mcpJwtSecretArn") as string | undefined;
    const certificateArn = this.node.tryGetContext("certificateArn") as string | undefined;
    const allowHttpForLocalSynth =
      (this.node.tryGetContext("allowHttpForLocalSynth") as string | undefined) === "true";
    if (!certificateArn && !allowHttpForLocalSynth) {
      throw new Error(
        "certificateArn is required for the internet-facing Remote MCP ALB. "
          + "Use -c allowHttpForLocalSynth=true only for local template inspection.",
      );
    }
    const mcpHostName =
      (this.node.tryGetContext("mcpHostName") as string | undefined) ??
      "underwriting-mcp.example.com";
    const hostedZoneName = this.node.tryGetContext("hostedZoneName") as string | undefined;
    const certificate = certificateArn
      ? acm.Certificate.fromCertificateArn(this, "McpCertificate", certificateArn)
      : undefined;
    const jwtSecret = configuredSecretArn
      ? secretsmanager.Secret.fromSecretCompleteArn(this, "JwtSecret", configuredSecretArn)
      : new secretsmanager.Secret(this, "JwtSecret", {
          description: "Demo MCP JWT HS256 signing secret",
          generateSecretString: { passwordLength: 48, excludePunctuation: true },
        });
    const service = new ecsPatterns.ApplicationLoadBalancedFargateService(this, "McpService", {
      cluster,
      publicLoadBalancer: true,
      certificate,
      protocol: certificate ? elbv2.ApplicationProtocol.HTTPS : elbv2.ApplicationProtocol.HTTP,
      redirectHTTP: Boolean(certificate),
      taskSubnets: {
        subnetType: lowCostDemo ? ec2.SubnetType.PUBLIC : ec2.SubnetType.PRIVATE_ISOLATED,
      },
      assignPublicIp: lowCostDemo,
      runtimePlatform: {
        cpuArchitecture: ecs.CpuArchitecture.ARM64,
        operatingSystemFamily: ecs.OperatingSystemFamily.LINUX,
      },
      desiredCount: 1,
      cpu: 512,
      memoryLimitMiB: 1024,
      circuitBreaker: { rollback: true },
      minHealthyPercent: 100,
      taskImageOptions: {
        image: ecs.ContainerImage.fromAsset(".", {
          file: "services/mcp-server/Dockerfile",
        }),
        containerPort: 8000,
        environment: {
          APP_MODE: "aws",
          AUTH_MODE: "jwt",
          ENVIRONMENT: "production",
          UNDERWRITING_BUCKET: props.bucket.bucketName,
          UNDERWRITING_JOBS_TABLE: props.table.tableName,
          UNDERWRITING_STATE_MACHINE_ARN: props.stateMachine.stateMachineArn,
          PUBLIC_BASE_URL: `${certificate ? "https" : "http"}://${mcpHostName}`,
          ALLOWED_HOSTS: mcpHostName,
          ALLOWED_ORIGINS: `https://claude.ai,https://${mcpHostName}`,
        },
        secrets: {
          MCP_JWT_SECRET: ecs.Secret.fromSecretsManager(jwtSecret),
        },
        logDriver: ecs.LogDrivers.awsLogs({
          streamPrefix: "underwriting-mcp",
          logRetention: logs.RetentionDays.ONE_WEEK,
        }),
      },
    });
    service.targetGroup.configureHealthCheck({ path: "/healthz" });
    props.bucket.grantReadWrite(service.taskDefinition.taskRole);
    props.table.grantReadWriteData(service.taskDefinition.taskRole);
    props.stateMachine.grantStartExecution(service.taskDefinition.taskRole);

    if (enableWaf) {
      const acl = new wafv2.CfnWebACL(this, "WebAcl", {
        defaultAction: { allow: {} },
        scope: "REGIONAL",
        visibilityConfig: {
          cloudWatchMetricsEnabled: true,
          metricName: "UnderwritingMcpWebAcl",
          sampledRequestsEnabled: true,
        },
        rules: [
          {
            name: "RateLimit",
            priority: 1,
            action: { block: {} },
            statement: { rateBasedStatement: { aggregateKeyType: "IP", limit: 1000 } },
            visibilityConfig: {
              cloudWatchMetricsEnabled: true,
              metricName: "RateLimit",
              sampledRequestsEnabled: true,
            },
          },
        ],
      });
      new wafv2.CfnWebACLAssociation(this, "WebAclAssociation", {
        resourceArn: service.loadBalancer.loadBalancerArn,
        webAclArn: acl.attrArn,
      });
    }

    if (hostedZoneName) {
      const zone = route53.HostedZone.fromLookup(this, "HostedZone", {
        domainName: hostedZoneName,
      });
      new route53.ARecord(this, "McpAliasRecord", {
        zone,
        recordName: mcpHostName,
        target: route53.RecordTarget.fromAlias(
          new route53Targets.LoadBalancerTarget(service.loadBalancer),
        ),
      });
    }

    new cdk.CfnOutput(this, "McpLoadBalancerDnsName", {
      value: service.loadBalancer.loadBalancerDnsName,
    });
    new cdk.CfnOutput(this, "DeploymentMode", { value: deploymentMode });
    new cdk.CfnOutput(this, "WafEnabled", { value: String(enableWaf) });
    new cdk.CfnOutput(this, "McpUrl", {
      value: `${certificate ? "https" : "http"}://${mcpHostName}/mcp`,
    });
    new cdk.CfnOutput(this, "McpJwtSecretName", {
      value: jwtSecret.secretName,
    });
  }
}
