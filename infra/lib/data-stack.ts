import * as cdk from "aws-cdk-lib";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as kms from "aws-cdk-lib/aws-kms";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

export class DataStack extends cdk.Stack {
  readonly bucket: s3.Bucket;
  readonly table: dynamodb.Table;
  readonly key: kms.Key;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.key = new kms.Key(this, "DataKey", {
      enableKeyRotation: true,
      alias: "alias/underwriting-mcp-demo",
    });

    this.bucket = new s3.Bucket(this, "ArtifactsBucket", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: this.key,
      enforceSSL: true,
      versioned: true,
      lifecycleRules: [{ expiration: cdk.Duration.days(1), prefix: "intake/" }],
    });

    this.table = new dynamodb.Table(this, "JobsTable", {
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: "expires_at",
      encryption: dynamodb.TableEncryption.CUSTOMER_MANAGED,
      encryptionKey: this.key,
    });

    const textractPrincipal = new iam.ServicePrincipal("textract.amazonaws.com");
    this.bucket.grantRead(textractPrincipal);
    this.key.grantDecrypt(textractPrincipal);
  }
}
