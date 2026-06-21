import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

export class NetworkStack extends cdk.Stack {
  readonly vpc: ec2.Vpc;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const deploymentMode =
      (this.node.tryGetContext("deploymentMode") as string | undefined) ?? "private";
    const lowCostDemo = deploymentMode === "demo-low-cost";

    this.vpc = new ec2.Vpc(this, "Vpc", {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        { name: "public", subnetType: ec2.SubnetType.PUBLIC },
        ...(!lowCostDemo
          ? [{ name: "private", subnetType: ec2.SubnetType.PRIVATE_ISOLATED }]
          : []),
      ],
    });

    if (lowCostDemo) {
      new cdk.CfnOutput(this, "DeploymentMode", { value: deploymentMode });
      return;
    }

    this.vpc.addGatewayEndpoint("S3Endpoint", { service: ec2.GatewayVpcEndpointAwsService.S3 });
    this.vpc.addGatewayEndpoint("DynamoEndpoint", {
      service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
    });
    const endpointServices = [
      ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
      ec2.InterfaceVpcEndpointAwsService.TEXTRACT,
      ec2.InterfaceVpcEndpointAwsService.STEP_FUNCTIONS,
      ec2.InterfaceVpcEndpointAwsService.ECR,
      ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
      ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
      ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
      ec2.InterfaceVpcEndpointAwsService.KMS,
      ec2.InterfaceVpcEndpointAwsService.STS,
    ];
    endpointServices.forEach((service, index) => {
      this.vpc.addInterfaceEndpoint(`InterfaceEndpoint${index}`, { service });
    });
  }
}
