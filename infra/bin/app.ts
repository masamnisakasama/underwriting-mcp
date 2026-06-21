#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { DataStack } from "../lib/data-stack";
import { McpStack } from "../lib/mcp-stack";
import { NetworkStack } from "../lib/network-stack";
import { WorkflowStack } from "../lib/workflow-stack";

const app = new cdk.App();
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};
const deploymentMode = (app.node.tryGetContext("deploymentMode") as string | undefined) ?? "private";
const lowCostDemo = deploymentMode === "demo-low-cost";

const network = new NetworkStack(app, "UnderwritingNetworkStack", { env });
const data = new DataStack(app, "UnderwritingDataStack", { env });
const workflow = new WorkflowStack(app, "UnderwritingWorkflowStack", {
  env,
  vpc: lowCostDemo ? undefined : network.vpc,
  bucket: data.bucket,
  table: data.table,
});
new McpStack(app, "UnderwritingMcpStack", {
  env,
  vpc: network.vpc,
  bucket: data.bucket,
  table: data.table,
  stateMachine: workflow.stateMachine,
});
