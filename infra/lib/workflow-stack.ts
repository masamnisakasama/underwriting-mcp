import * as cdk from "aws-cdk-lib";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as sfn from "aws-cdk-lib/aws-stepfunctions";
import * as tasks from "aws-cdk-lib/aws-stepfunctions-tasks";
import { Construct } from "constructs";

export interface WorkflowStackProps extends cdk.StackProps {
  vpc?: ec2.IVpc;
  bucket: s3.IBucket;
  table: dynamodb.ITable;
}

export class WorkflowStack extends cdk.Stack {
  readonly stateMachine: sfn.StateMachine;

  constructor(scope: Construct, id: string, props: WorkflowStackProps) {
    super(scope, id, props);

    const bedrockModelId =
      (this.node.tryGetContext("bedrockModelId") as string | undefined) ?? "";
    const deploymentMode =
      (this.node.tryGetContext("deploymentMode") as string | undefined) ?? "private";
    const lowCostDemo = deploymentMode === "demo-low-cost";

    const worker = new lambda.DockerImageFunction(this, "UnderwritingWorkflowWorker", {
      code: lambda.DockerImageCode.fromImageAsset(".", {
        file: "lambdas/underwriting_workflow/Dockerfile",
      }),
      architecture: lambda.Architecture.ARM_64,
      timeout: cdk.Duration.minutes(15),
      memorySize: 2048,
      ...(props.vpc
        ? {
            vpc: props.vpc,
            vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
          }
        : {}),
      environment: {
        UNDERWRITING_BUCKET: props.bucket.bucketName,
        UNDERWRITING_JOBS_TABLE: props.table.tableName,
        BEDROCK_MODEL_ID: bedrockModelId,
        TEXTRACT_WAIT_SECONDS: "240",
        ...(lowCostDemo
          ? { DEMO_TEXTRACT_STUB: "1", DISABLE_BEDROCK_NORMALIZATION: "1" }
          : {}),
      },
    });
    props.bucket.grantReadWrite(worker);
    props.table.grantReadWriteData(worker);
    worker.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "textract:StartDocumentAnalysis",
          "textract:GetDocumentAnalysis",
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ],
        resources: ["*"],
      }),
    );

    const validateCase = new tasks.LambdaInvoke(this, "ValidateCase", {
      lambdaFunction: worker,
      payload: sfn.TaskInput.fromObject({
        action: "validate_case",
        case_id: sfn.JsonPath.stringAt("$.case_id"),
        job_id: sfn.JsonPath.stringAt("$.job_id"),
        ruleset_version: sfn.JsonPath.stringAt("$.ruleset_version"),
      }),
      outputPath: "$.Payload",
    });

    const processDocument = new tasks.LambdaInvoke(this, "ProcessDocument", {
      lambdaFunction: worker,
      payload: sfn.TaskInput.fromObject({
        action: "process_document",
        case_id: sfn.JsonPath.stringAt("$.case_id"),
        job_id: sfn.JsonPath.stringAt("$.job_id"),
        document: sfn.JsonPath.objectAt("$.document"),
      }),
      outputPath: "$.Payload",
    });

    const processDocuments = new sfn.Map(this, "ProcessDocumentsInParallel", {
      itemsPath: "$.documents",
      itemSelector: {
        "case_id.$": "$.case_id",
        "job_id.$": "$.job_id",
        "document.$": "$$.Map.Item.Value",
      },
      resultPath: "$.document_artifacts",
      maxConcurrency: 3,
    });
    processDocuments.itemProcessor(processDocument);

    const normalize = new tasks.LambdaInvoke(this, "InvokeBedrockForNormalization", {
      lambdaFunction: worker,
      payload: sfn.TaskInput.fromObject({
        action: "normalize",
        case_id: sfn.JsonPath.stringAt("$.case_id"),
        job_id: sfn.JsonPath.stringAt("$.job_id"),
        ruleset_version: sfn.JsonPath.stringAt("$.ruleset_version"),
        product_code: sfn.JsonPath.stringAt("$.product_code"),
        document_artifacts: sfn.JsonPath.listAt("$.document_artifacts"),
      }),
      outputPath: "$.Payload",
    });

    const assemble = new tasks.LambdaInvoke(this, "AssembleFinalResult", {
      lambdaFunction: worker,
      payload: sfn.TaskInput.fromObject({
        action: "assemble",
        case_id: sfn.JsonPath.stringAt("$.case_id"),
        job_id: sfn.JsonPath.stringAt("$.job_id"),
        ruleset_version: sfn.JsonPath.stringAt("$.ruleset_version"),
        facts_uri: sfn.JsonPath.stringAt("$.facts_uri"),
      }),
      outputPath: "$.Payload",
    });

    const markFailed = new tasks.LambdaInvoke(this, "MarkJobFailed", {
      lambdaFunction: worker,
      payload: sfn.TaskInput.fromObject({
        action: "mark_failed",
        job_id: sfn.JsonPath.stringAt("$.job_id"),
        error: sfn.JsonPath.objectAt("$.error"),
      }),
      outputPath: "$.Payload",
    });
    const fail = new sfn.Fail(this, "WorkflowFailed");
    markFailed.next(fail);
    for (const state of [validateCase, normalize, assemble]) {
      state.addCatch(markFailed, { resultPath: "$.error" });
    }
    processDocuments.addCatch(markFailed, { resultPath: "$.error" });

    this.stateMachine = new sfn.StateMachine(this, "UnderwritingWorkflow", {
      definitionBody: sfn.DefinitionBody.fromChainable(
        validateCase.next(processDocuments).next(normalize).next(assemble),
      ),
      stateMachineType: sfn.StateMachineType.STANDARD,
    });
  }
}
