"""
Main CDK stack for DMARC Lens infrastructure.
"""

from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_notifications as s3_notifications,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    aws_dynamodb as dynamodb,
    aws_ses as ses,
    aws_ses_actions as ses_actions,
    aws_apigateway as apigateway,
    aws_apigatewayv2 as apigatewayv2,
    aws_apigatewayv2_integrations as apigatewayv2_integrations,
    aws_apigatewayv2_authorizers as apigatewayv2_authorizers,
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
        
        # Create Lambda functions for processing
        self._create_lambda_functions()
        
        # Set up Cognito for user authentication
        self._create_cognito_authentication()
        
        # Create API Gateway and Lambda functions for data access
        self._create_api_gateway()

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
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # Keep private for now
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

    def _create_lambda_functions(self) -> None:
        """
        Create Lambda functions for processing and analysis.
        
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5
        - Create Report Parser Lambda function
        - Create Analysis Engine Lambda function
        - Set up S3 event notifications and DynamoDB streams
        """
        
        # Report Parser Lambda Function
        self.report_parser_lambda = _lambda.Function(
            self,
            "ReportParserFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="dmarc_lens.lambda_functions.report_parser.lambda_handler",
            code=_lambda.Code.from_asset("../src"),
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "REPORTS_TABLE_NAME": self.reports_table.table_name,
                "FAILED_REPORTS_TABLE_NAME": "dmarc-failed-reports",
                "LOG_LEVEL": "INFO"
            },
            description="Processes DMARC report emails from S3 and stores parsed data in DynamoDB"
        )
        
        # Grant permissions to Report Parser Lambda
        self.raw_email_bucket.grant_read(self.report_parser_lambda)
        self.reports_table.grant_write_data(self.report_parser_lambda)
        
        # Create failed reports table for error handling
        self.failed_reports_table = dynamodb.Table(
            self,
            "FailedReportsTable",
            table_name="dmarc-failed-reports",
            partition_key=dynamodb.Attribute(
                name="failure_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            encryption=dynamodb.TableEncryption.AWS_MANAGED
        )
        
        self.failed_reports_table.grant_write_data(self.report_parser_lambda)
        
        # Add S3 event notification to trigger Report Parser
        self.raw_email_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3_notifications.LambdaDestination(self.report_parser_lambda),
            s3.NotificationKeyFilter(prefix="incoming/")
        )
        
        # Analysis Engine Lambda Function
        self.analysis_engine_lambda = _lambda.Function(
            self,
            "AnalysisEngineFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="dmarc_lens.lambda_functions.analysis_engine.lambda_handler",
            code=_lambda.Code.from_asset("../src"),
            timeout=Duration.minutes(2),
            memory_size=256,
            environment={
                "ANALYSIS_TABLE_NAME": self.analysis_table.table_name,
                "LOG_LEVEL": "INFO"
            },
            description="Analyzes DMARC report data and generates insights"
        )
        
        # Grant permissions to Analysis Engine Lambda
        self.reports_table.grant_read_data(self.analysis_engine_lambda)
        self.analysis_table.grant_read_write_data(self.analysis_engine_lambda)
        
        # Add DynamoDB Stream event source to trigger Analysis Engine
        self.analysis_engine_lambda.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self.reports_table,
                starting_position=_lambda.StartingPosition.LATEST,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
                retry_attempts=3
            )
        )

    def _create_api_gateway(self) -> None:
        """
        Create API Gateway HTTP API with authentication and Lambda integrations.
        
        Requirements: 4.4, 6.3
        - Set up HTTP API with Cognito JWT authorizer
        - Configure CORS for web application access
        - Implement rate limiting and throttling
        """
        
        # Create HTTP API Gateway
        self.http_api = apigatewayv2.HttpApi(
            self,
            "DmarcLensApi",
            api_name="dmarc-lens-api",
            description="DMARC Lens REST API for data access",
            cors_preflight=apigatewayv2.CorsPreflightOptions(
                allow_origins=["http://localhost:3000", "https://yourdomain.com"],  # Configure with actual domains
                allow_methods=[
                    apigatewayv2.CorsHttpMethod.GET,
                    apigatewayv2.CorsHttpMethod.POST,
                    apigatewayv2.CorsHttpMethod.PUT,
                    apigatewayv2.CorsHttpMethod.DELETE,
                    apigatewayv2.CorsHttpMethod.OPTIONS
                ],
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token"
                ],
                allow_credentials=True,
                max_age=Duration.hours(1)
            )
        )

        # Create JWT Authorizer using Cognito User Pool
        self.jwt_authorizer = apigatewayv2_authorizers.HttpJwtAuthorizer(
            "CognitoJwtAuthorizer",
            jwt_audience=[self.user_pool_client.user_pool_client_id],
            jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}",
            identity_source=["$request.header.Authorization"]
        )

        # Create throttling configuration
        self.throttle_config = apigatewayv2.ThrottleConfig(
            rate_limit=1000,  # requests per second
            burst_limit=2000  # burst capacity
        )

        # Create default stage with throttling
        self.api_stage = apigatewayv2.HttpStage(
            self,
            "DmarcLensApiStage",
            http_api=self.http_api,
            stage_name="prod",
            auto_deploy=True,
            throttle=self.throttle_config
        )

        # Store API endpoint for outputs
        self.api_endpoint = self.http_api.api_endpoint
        
        # Create Lambda functions for API endpoints
        self._create_api_lambda_functions()
        
        # Create API routes and integrations
        self._create_api_routes()
    def _create_api_lambda_functions(self) -> None:
        """
        Create Lambda functions for API endpoints.
        
        Requirements: 6.1, 6.2, 6.4
        - Create Data API Lambda function
        - Create Authentication Lambda function
        - Grant necessary permissions
        """
        
        # Data API Lambda Function
        self.data_api_lambda = _lambda.Function(
            self,
            "DataApiFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="dmarc_lens.lambda_functions.data_api.lambda_handler",
            code=_lambda.Code.from_asset("../src"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "REPORTS_TABLE_NAME": self.reports_table.table_name,
                "ANALYSIS_TABLE_NAME": self.analysis_table.table_name,
                "LOG_LEVEL": "INFO"
            },
            description="Provides REST API endpoints for DMARC data access"
        )
        
        # Grant permissions to Data API Lambda
        self.reports_table.grant_read_data(self.data_api_lambda)
        self.analysis_table.grant_read_data(self.data_api_lambda)
        
        # Authentication Lambda Function (will be implemented in next subtask)
        self.auth_lambda = _lambda.Function(
            self,
            "AuthFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="dmarc_lens.lambda_functions.auth.lambda_handler",
            code=_lambda.Code.from_asset("../src"),
            timeout=Duration.seconds(10),
            memory_size=128,
            environment={
                "USER_POOL_ID": self.user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": self.user_pool_client.user_pool_client_id,
                "LOG_LEVEL": "INFO"
            },
            description="Handles JWT token validation and authorization"
        )
        
        # Grant permissions to Authentication Lambda
        self.auth_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:GetUser",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:ListUsers"
                ],
                resources=[self.user_pool.user_pool_arn]
            )
        )

    def _create_api_routes(self) -> None:
        """
        Create API Gateway routes and integrations.
        
        Requirements: 6.1, 6.2, 6.4
        - Create routes for reports, analysis, and dashboard endpoints
        - Configure Lambda integrations with authentication
        - Set up proper HTTP methods and paths
        """
        
        # Create Lambda integrations
        data_api_integration = apigatewayv2_integrations.HttpLambdaIntegration(
            "DataApiIntegration",
            self.data_api_lambda
        )
        
        auth_integration = apigatewayv2_integrations.HttpLambdaIntegration(
            "AuthIntegration",
            self.auth_lambda
        )
        
        # Reports endpoints
        self.http_api.add_routes(
            path="/reports",
            methods=[apigatewayv2.HttpMethod.GET],
            integration=data_api_integration,
            authorizer=self.jwt_authorizer
        )
        
        self.http_api.add_routes(
            path="/reports/{report_id}",
            methods=[apigatewayv2.HttpMethod.GET],
            integration=data_api_integration,
            authorizer=self.jwt_authorizer
        )
        
        # Analysis endpoints
        self.http_api.add_routes(
            path="/analysis/{domain}",
            methods=[apigatewayv2.HttpMethod.GET],
            integration=data_api_integration,
            authorizer=self.jwt_authorizer
        )
        
        # Dashboard endpoint
        self.http_api.add_routes(
            path="/dashboard",
            methods=[apigatewayv2.HttpMethod.GET],
            integration=data_api_integration,
            authorizer=self.jwt_authorizer
        )
        
        # Authentication endpoints (public)
        self.http_api.add_routes(
            path="/auth/validate",
            methods=[apigatewayv2.HttpMethod.POST],
            integration=auth_integration
        )
        
        # Health check endpoint (public)
        self.http_api.add_routes(
            path="/health",
            methods=[apigatewayv2.HttpMethod.GET],
            integration=data_api_integration
        )