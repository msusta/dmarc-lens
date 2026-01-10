"""
Main CDK stack for DMARC Lens infrastructure.
"""

from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_ses as ses,
    aws_ses_actions as ses_actions,
    aws_apigateway as apigateway,
    aws_cognito as cognito,
    aws_cloudfront as cloudfront,
    aws_iam as iam,
    RemovalPolicy,
    Duration
)
from constructs import Construct


class DmarcLensStack(Stack):
    """
    CDK Stack for DMARC Lens serverless infrastructure.
    
    This stack creates all AWS resources needed for the DMARC analysis platform:
    - S3 buckets for email storage and web hosting
    - Lambda functions for processing and API
    - DynamoDB tables for data storage
    - SES configuration for email ingestion
    - API Gateway for REST API
    - Cognito for authentication
    - CloudFront for web distribution
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 buckets for email storage and web hosting
        self._create_s3_buckets()
        
        # Set up SES email receiving configuration
        self._create_ses_configuration()
        
        # Create DynamoDB tables for reports and analysis
        self._create_dynamodb_tables()
        
        # Set up Cognito for user authentication
        self._create_cognito_authentication()

    def _create_s3_buckets(self) -> None:
        """
        Create S3 buckets for email storage and web hosting.
        
        Requirements: 1.1, 1.3
        - Raw email bucket with lifecycle policies
        - Static website bucket for React app
        - Configure bucket policies and encryption
        """
        
        # Raw email storage bucket
        self.raw_email_bucket = s3.Bucket(
            self,
            "RawEmailBucket",
            bucket_name=f"dmarc-lens-raw-emails-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldEmails",
                    enabled=True,
                    expiration=Duration.days(365),  # Keep emails for 1 year
                    noncurrent_version_expiration=Duration.days(30)
                ),
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ]
        )

        # Static website hosting bucket for React app
        self.web_hosting_bucket = s3.Bucket(
            self,
            "WebHostingBucket",
            bucket_name=f"dmarc-lens-web-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            website_index_document="index.html",
            website_error_document="error.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False
            ),
            removal_policy=RemovalPolicy.DESTROY,  # Can be recreated
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldVersions",
                    enabled=True,
                    noncurrent_version_expiration=Duration.days(7)
                )
            ]
        )

        # Create bucket policy for SES to write to raw email bucket
        self.raw_email_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowSESPuts",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("ses.amazonaws.com")],
                actions=["s3:PutObject"],
                resources=[f"{self.raw_email_bucket.bucket_arn}/*"],
                conditions={
                    "StringEquals": {
                        "aws:Referer": self.account
                    }
                }
            )
        )

    def _create_ses_configuration(self) -> None:
        """
        Set up SES email receiving configuration.
        
        Requirements: 1.1, 1.2
        - Configure SES to receive emails and store in S3
        - Create receipt rules and actions
        - Set up S3 event notifications to trigger Lambda
        """
        
        # Create SES receipt rule set
        self.receipt_rule_set = ses.ReceiptRuleSet(
            self,
            "DmarcReportsRuleSet",
            receipt_rule_set_name="dmarc-reports-ruleset"
        )

        # Create SES receipt rule for DMARC reports
        self.receipt_rule = ses.ReceiptRule(
            self,
            "DmarcReportsRule",
            rule_set=self.receipt_rule_set,
            receipt_rule_name="dmarc-reports-rule",
            enabled=True,
            scan_enabled=True,  # Enable spam and virus scanning
            tls_policy=ses.TlsPolicy.REQUIRE,  # Require TLS
            recipients=["dmarc-reports@yourdomain.com"],  # Configure with actual domain
            actions=[
                ses_actions.S3(
                    bucket=self.raw_email_bucket,
                    object_key_prefix="incoming/",
                    topic=None  # Will add SNS topic later if needed
                )
            ]
        )

        # Add S3 event notification to trigger Lambda processing
        # Note: Lambda function will be created in task 4, so we'll store the bucket reference
        # The actual notification will be configured when the Lambda is created

    def _create_dynamodb_tables(self) -> None:
        """
        Create DynamoDB tables for reports and analysis.
        
        Requirements: 2.3, 3.4
        - Define Reports table with partition key (report_id) and sort key (record_id)
        - Define Analysis table with partition key (domain) and sort key (analysis_date)
        - Configure DynamoDB Streams for triggering analysis
        """
        
        # Reports table for storing parsed DMARC report data
        self.reports_table = dynamodb.Table(
            self,
            "ReportsTable",
            table_name="dmarc-reports",
            partition_key=dynamodb.Attribute(
                name="report_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="record_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,  # Enable streams for analysis
            removal_policy=RemovalPolicy.RETAIN,  # Keep data for compliance
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            encryption=dynamodb.TableEncryption.AWS_MANAGED
        )

        # Add Global Secondary Index for querying by domain
        self.reports_table.add_global_secondary_index(
            index_name="domain-index",
            partition_key=dynamodb.Attribute(
                name="domain",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.NUMBER
            )
        )

        # Add Global Secondary Index for querying by date range
        self.reports_table.add_global_secondary_index(
            index_name="date-index",
            partition_key=dynamodb.Attribute(
                name="date_range_begin",
                type=dynamodb.AttributeType.NUMBER
            ),
            sort_key=dynamodb.Attribute(
                name="domain",
                type=dynamodb.AttributeType.STRING
            )
        )

        # Analysis table for storing analysis results and insights
        self.analysis_table = dynamodb.Table(
            self,
            "AnalysisTable",
            table_name="dmarc-analysis",
            partition_key=dynamodb.Attribute(
                name="domain",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="analysis_date",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            encryption=dynamodb.TableEncryption.AWS_MANAGED
        )

        # Add Global Secondary Index for querying latest analysis across domains
        self.analysis_table.add_global_secondary_index(
            index_name="latest-analysis-index",
            partition_key=dynamodb.Attribute(
                name="analysis_type",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="analysis_date",
                type=dynamodb.AttributeType.STRING
            )
        )

    def _create_cognito_authentication(self) -> None:
        """
        Set up Cognito for user authentication.
        
        Requirements: 4.1, 4.2, 4.3
        - Create Cognito User Pool and Identity Pool
        - Configure JWT token settings and user attributes
        - Set up authentication flows for web application
        """
        
        # Create Cognito User Pool
        self.user_pool = cognito.UserPool(
            self,
            "DmarcLensUserPool",
            user_pool_name="dmarc-lens-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=True
            ),
            auto_verify=cognito.AutoVerifiedAttrs(
                email=True
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                ),
                given_name=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                ),
                family_name=cognito.StandardAttribute(
                    required=True,
                    mutable=True
                )
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.RETAIN
        )

        # Create User Pool Client for web application
        self.user_pool_client = cognito.UserPoolClient(
            self,
            "DmarcLensWebClient",
            user_pool=self.user_pool,
            user_pool_client_name="dmarc-lens-web-client",
            generate_secret=False,  # Public client for SPA
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                custom=True,
                admin_user_password=True
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE
                ],
                callback_urls=["http://localhost:3000", "https://yourdomain.com"],  # Configure with actual domains
                logout_urls=["http://localhost:3000", "https://yourdomain.com"]
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ],
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30)
        )

        # Create User Pool Domain for hosted UI
        self.user_pool_domain = cognito.UserPoolDomain(
            self,
            "DmarcLensUserPoolDomain",
            user_pool=self.user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix="dmarc-lens"  # Will be dmarc-lens.auth.region.amazoncognito.com
            )
        )

        # Create Identity Pool for AWS resource access
        self.identity_pool = cognito.CfnIdentityPool(
            self,
            "DmarcLensIdentityPool",
            identity_pool_name="dmarc-lens-identity-pool",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=self.user_pool_client.user_pool_client_id,
                    provider_name=self.user_pool.user_pool_provider_name
                )
            ]
        )

        # Create IAM roles for authenticated users
        self.authenticated_role = iam.Role(
            self,
            "CognitoAuthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": self.identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    }
                }
            ),
            inline_policies={
                "CognitoAuthenticatedPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "cognito-sync:*",
                                "cognito-identity:*"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # Attach the role to the identity pool
        cognito.CfnIdentityPoolRoleAttachment(
            self,
            "IdentityPoolRoleAttachment",
            identity_pool_id=self.identity_pool.ref,
            roles={
                "authenticated": self.authenticated_role.role_arn
            }
        )