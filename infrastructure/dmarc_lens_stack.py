"""
Main CDK stack for DMARC Lens infrastructure.
"""

import json
import os
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
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_iam as iam,
    aws_logs as logs,
    RemovalPolicy,
    Duration,
    CfnOutput,
    Tags
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

        # Load environment configuration
        self.env_name = self.node.try_get_context("environment") or "dev"
        self.config = self._load_environment_config()
        
        # Apply tags to all resources
        self._apply_tags()

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
        
        # Set up CloudFront distribution for web app
        self._create_cloudfront_distribution()

    def _load_environment_config(self) -> dict:
        """Load environment-specific configuration from JSON file."""
        config_path = os.path.join(
            os.path.dirname(__file__), 
            "environments", 
            f"{self.env_name}.json"
        )
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise ValueError(f"Environment configuration not found: {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in environment configuration: {e}")

    def _apply_tags(self) -> None:
        """Apply environment-specific tags to all resources."""
        tags = self.config.get("tags", {})
        for key, value in tags.items():
            Tags.of(self).add(key, value)

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
            bucket_name=f"dmarc-lens-raw-emails-{self.env_name}-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN if self.env_name == "prod" else RemovalPolicy.DESTROY,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldEmails",
                    enabled=True,
                    expiration=Duration.days(365 if self.env_name == "prod" else 30),
                    noncurrent_version_expiration=Duration.days(30 if self.env_name == "prod" else 7)
                ),
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30 if self.env_name == "prod" else 7)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90 if self.env_name == "prod" else 14)
                        )
                    ]
                )
            ]
        )

        # Static website hosting bucket for React app
        self.web_hosting_bucket = s3.Bucket(
            self,
            "WebHostingBucket",
            bucket_name=f"dmarc-lens-web-{self.env_name}-{self.account}-{self.region}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
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
            receipt_rule_set_name=f"dmarc-reports-ruleset-{self.env_name}"
        )

        # Get email addresses from environment configuration
        email_addresses = self.config.get("ses", {}).get("email_addresses", [])
        if not email_addresses:
            raise ValueError("No SES email addresses configured for environment")

        # Create SES receipt rule for DMARC reports
        self.receipt_rule = ses.ReceiptRule(
            self,
            "DmarcReportsRule",
            rule_set=self.receipt_rule_set,
            receipt_rule_name=f"dmarc-reports-rule-{self.env_name}",
            enabled=True,
            scan_enabled=True,  # Enable spam and virus scanning
            tls_policy=ses.TlsPolicy.REQUIRE,  # Require TLS
            recipients=email_addresses,
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
            table_name=f"dmarc-reports-{self.env_name}",
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
            removal_policy=RemovalPolicy.RETAIN if self.env_name == "prod" else RemovalPolicy.DESTROY,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=self.env_name == "prod"
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
            table_name=f"dmarc-analysis-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="domain",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="analysis_date",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN if self.env_name == "prod" else RemovalPolicy.DESTROY,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=self.env_name == "prod"
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
            user_pool_name=f"dmarc-lens-users-{self.env_name}",
            self_sign_up_enabled=False,
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
            removal_policy=RemovalPolicy.RETAIN if self.env_name == "prod" else RemovalPolicy.DESTROY
        )

        # Get callback and logout URLs from environment configuration
        callback_urls = self.config.get("cognito", {}).get("callback_urls", ["http://localhost:3000"])
        logout_urls = self.config.get("cognito", {}).get("logout_urls", ["http://localhost:3000"])

        # Create User Pool Client for web application
        self.user_pool_client = cognito.UserPoolClient(
            self,
            "DmarcLensWebClient",
            user_pool=self.user_pool,
            user_pool_client_name=f"dmarc-lens-web-client-{self.env_name}",
            generate_secret=False,  # Public client for SPA
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                custom=False,
                admin_user_password=False
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=False
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE
                ],
                callback_urls=callback_urls,
                logout_urls=logout_urls
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
                domain_prefix=f"dmarc-lens-{self.env_name}"
            )
        )

        # Create Identity Pool for AWS resource access
        self.identity_pool = cognito.CfnIdentityPool(
            self,
            "DmarcLensIdentityPool",
            identity_pool_name=f"dmarc-lens-identity-pool-{self.env_name}",
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
                                "cognito-sync:GetCognitoEvents",
                                "cognito-sync:ListRecords",
                                "cognito-sync:QueryRecords",
                                "cognito-identity:GetId",
                                "cognito-identity:GetCredentialsForIdentity"
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
                "FAILED_REPORTS_TABLE_NAME": f"dmarc-failed-reports-{self.env_name}",
                "LOG_LEVEL": "INFO" if self.env_name == "prod" else "DEBUG",
                "ENVIRONMENT": self.env_name
            },
            description=f"Processes DMARC report emails from S3 and stores parsed data in DynamoDB ({self.env_name})",
            log_retention=logs.RetentionDays.ONE_MONTH if self.env_name == "prod" else logs.RetentionDays.ONE_WEEK
        )
        
        # Grant permissions to Report Parser Lambda
        self.raw_email_bucket.grant_read(self.report_parser_lambda)
        self.reports_table.grant_write_data(self.report_parser_lambda)
        
        # Create failed reports table for error handling
        self.failed_reports_table = dynamodb.Table(
            self,
            "FailedReportsTable",
            table_name=f"dmarc-failed-reports-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="failure_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN if self.env_name == "prod" else RemovalPolicy.DESTROY,
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
                "LOG_LEVEL": "INFO" if self.env_name == "prod" else "DEBUG",
                "ENVIRONMENT": self.env_name
            },
            description=f"Analyzes DMARC report data and generates insights ({self.env_name})",
            log_retention=logs.RetentionDays.ONE_MONTH if self.env_name == "prod" else logs.RetentionDays.ONE_WEEK
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
            api_name=f"dmarc-lens-api-{self.env_name}",
            description=f"DMARC Lens REST API for data access ({self.env_name})",
            cors_preflight=apigatewayv2.CorsPreflightOptions(
                allow_origins=self.config.get("api", {}).get("cors_origins", ["http://localhost:3000"]),
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

        ## Create throttling configuration
        #self.throttle_config = apigatewayv2.ThrottleConfig(
        #    rate_limit=1000,  # requests per second
        #    burst_limit=2000  # burst capacity
        #)

        # Create default stage with throttling
        self.api_stage = apigatewayv2.HttpStage(
            self,
            "DmarcLensApiStage",
            http_api=self.http_api,
            stage_name=self.env_name,
            auto_deploy=True,
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
                "CORS_ORIGIN": self.config.get("api", {}).get("cors_origins", ["http://localhost:3000"])[0],
                "LOG_LEVEL": "INFO" if self.env_name == "prod" else "DEBUG",
                "ENVIRONMENT": self.env_name
            },
            description=f"Provides REST API endpoints for DMARC data access ({self.env_name})",
            log_retention=logs.RetentionDays.ONE_MONTH if self.env_name == "prod" else logs.RetentionDays.ONE_WEEK
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
                "CORS_ORIGIN": self.config.get("api", {}).get("cors_origins", ["http://localhost:3000"])[0],
                "LOG_LEVEL": "INFO" if self.env_name == "prod" else "DEBUG",
                "ENVIRONMENT": self.env_name
            },
            description=f"Handles JWT token validation and authorization ({self.env_name})",
            log_retention=logs.RetentionDays.ONE_MONTH if self.env_name == "prod" else logs.RetentionDays.ONE_WEEK
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

    def _create_cloudfront_distribution(self) -> None:
        """
        Set up CloudFront distribution for web app.
        
        Requirements: 5.1, 5.2, 5.3
        - Configure CloudFront for S3 static website hosting
        - Set up custom domain and SSL certificate
        - Configure caching policies for optimal performance
        """
        
        # Create S3 origin for the web hosting bucket
        s3_origin = cloudfront.OriginAccessIdentity(
            self,
            "WebOriginAccessIdentity",
            comment=f"Origin Access Identity for DMARC Lens web app ({self.env_name})"
        )
        
        # Grant CloudFront access to S3 bucket
        self.web_hosting_bucket.grant_read(s3_origin)
        
        # Get domain configuration
        domain_config = self.config.get("domain", {})
        domain_enabled = domain_config.get("enabled", False)
        domain_name = domain_config.get("domain_name", "")
        certificate_arn = domain_config.get("certificate_arn", "")
        
        # Configure domain names and certificate if enabled
        viewer_certificate = None
        if domain_enabled and domain_name and certificate_arn:
            viewer_certificate = cloudfront.ViewerCertificate.from_acm_certificate(
                acm.Certificate.from_certificate_arn(self, "Certificate", certificate_arn),
                aliases=[domain_name],
                ssl_method=cloudfront.SSLMethod.SNI,
                security_policy=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021
            )
        else:
            viewer_certificate = cloudfront.ViewerCertificate.from_cloud_front_default_certificate()
        
        # Create API Gateway origin for API calls
        api_domain = f"{self.http_api.http_api_id}.execute-api.{self.region}.amazonaws.com"
        
        # Create CloudFront distribution
        self.cloudfront_distribution = cloudfront.CloudFrontWebDistribution(
            self,
            "WebDistribution",
            comment=f"DMARC Lens web application distribution ({self.env_name})",
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,  # Use only North America and Europe
            viewer_certificate=viewer_certificate,
            
            # Origin configurations
            origin_configs=[
                cloudfront.SourceConfiguration(
                    s3_origin_source=cloudfront.S3OriginConfig(
                        s3_bucket_source=self.web_hosting_bucket,
                        origin_access_identity=s3_origin
                    ),
                    behaviors=[
                        # Default behavior for HTML files
                        cloudfront.Behavior(
                            is_default_behavior=True,
                            allowed_methods=cloudfront.CloudFrontAllowedMethods.GET_HEAD,
                            cached_methods=cloudfront.CloudFrontAllowedCachedMethods.GET_HEAD,
                            compress=True,
                            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                            default_ttl=Duration.minutes(5),
                            max_ttl=Duration.hours(1),
                            min_ttl=Duration.seconds(0)
                        ),
                        # Static assets behavior
                        cloudfront.Behavior(
                            path_pattern="/static/*",
                            allowed_methods=cloudfront.CloudFrontAllowedMethods.GET_HEAD,
                            cached_methods=cloudfront.CloudFrontAllowedCachedMethods.GET_HEAD,
                            compress=True,
                            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                            default_ttl=Duration.days(30),
                            max_ttl=Duration.days(365),
                            min_ttl=Duration.seconds(0)
                        )
                    ]
                ),
                # API Gateway origin configuration
                cloudfront.SourceConfiguration(
                    custom_origin_source=cloudfront.CustomOriginConfig(
                        domain_name=api_domain,
                        origin_path=f"/{self.env_name}",
                        http_port=80,
                        https_port=443,
                        origin_protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY
                    ),
                    behaviors=[
                        cloudfront.Behavior(
                            path_pattern="/reports*",
                            allowed_methods=cloudfront.CloudFrontAllowedMethods.ALL,
                            cached_methods=cloudfront.CloudFrontAllowedCachedMethods.GET_HEAD,
                            compress=True,
                            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                            default_ttl=Duration.seconds(0),
                            max_ttl=Duration.seconds(0),
                            min_ttl=Duration.seconds(0)
                        ),
                        cloudfront.Behavior(
                            path_pattern="/analysis*",
                            allowed_methods=cloudfront.CloudFrontAllowedMethods.ALL,
                            cached_methods=cloudfront.CloudFrontAllowedCachedMethods.GET_HEAD,
                            compress=True,
                            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                            default_ttl=Duration.seconds(0),
                            max_ttl=Duration.seconds(0),
                            min_ttl=Duration.seconds(0)
                        ),
                        cloudfront.Behavior(
                            path_pattern="/dashboard",
                            allowed_methods=cloudfront.CloudFrontAllowedMethods.ALL,
                            cached_methods=cloudfront.CloudFrontAllowedCachedMethods.GET_HEAD,
                            compress=True,
                            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                            default_ttl=Duration.seconds(0),
                            max_ttl=Duration.seconds(0),
                            min_ttl=Duration.seconds(0)
                        ),
                        cloudfront.Behavior(
                            path_pattern="/auth/*",
                            allowed_methods=cloudfront.CloudFrontAllowedMethods.ALL,
                            cached_methods=cloudfront.CloudFrontAllowedCachedMethods.GET_HEAD,
                            compress=True,
                            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                            default_ttl=Duration.seconds(0),
                            max_ttl=Duration.seconds(0),
                            min_ttl=Duration.seconds(0)
                        ),
                        cloudfront.Behavior(
                            path_pattern="/health",
                            allowed_methods=cloudfront.CloudFrontAllowedMethods.GET_HEAD,
                            cached_methods=cloudfront.CloudFrontAllowedCachedMethods.GET_HEAD,
                            compress=True,
                            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                            default_ttl=Duration.seconds(0),
                            max_ttl=Duration.seconds(0),
                            min_ttl=Duration.seconds(0)
                        )
                    ]
                )
            ],
            
            # Error configurations for SPA routing
            error_configurations=[
                cloudfront.CfnDistribution.CustomErrorResponseProperty(
                    error_code=404,
                    response_code=200,
                    response_page_path="/index.html",
                    error_caching_min_ttl=300
                ),
                cloudfront.CfnDistribution.CustomErrorResponseProperty(
                    error_code=403,
                    response_code=200,
                    response_page_path="/index.html",
                    error_caching_min_ttl=300
                )
            ],
            
            # Default root object
            default_root_object="index.html"
        )
        
        # Store CloudFront domain name for outputs
        self.cloudfront_domain_name = self.cloudfront_distribution.distribution_domain_name
        
        # Output the CloudFront distribution URL
        website_url = f"https://{domain_name}" if domain_enabled and domain_name else f"https://{self.cloudfront_domain_name}"
        CfnOutput(
            self,
            "WebsiteUrl",
            value=website_url,
            description="Website URL for the DMARC Lens application"
        )
        
        # Output the CloudFront distribution URL
        CfnOutput(
            self,
            "CloudFrontDistributionUrl",
            value=f"https://{self.cloudfront_domain_name}",
            description="CloudFront distribution URL for the web application"
        )
        
        # Output the CloudFront distribution ID for deployment scripts
        CfnOutput(
            self,
            "CloudFrontDistributionId",
            value=self.cloudfront_distribution.distribution_id,
            description="CloudFront distribution ID for cache invalidation"
        )
        
        # Output the web hosting bucket name for deployment scripts
        CfnOutput(
            self,
            "WebHostingBucketName",
            value=self.web_hosting_bucket.bucket_name,
            description="S3 bucket name for web hosting"
        )
        
        # Output API Gateway endpoint for frontend configuration
        CfnOutput(
            self,
            "ApiEndpoint",
            value=f"{self.api_endpoint}/{self.env_name}",
            description="API Gateway endpoint URL (with stage)"
        )
        
        # Output Cognito User Pool ID for frontend configuration
        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )
        
        # Output Cognito User Pool Client ID for frontend configuration
        CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID"
        )
        
        # Output Cognito Identity Pool ID for frontend configuration
        CfnOutput(
            self,
            "IdentityPoolId",
            value=self.identity_pool.ref,
            description="Cognito Identity Pool ID"
        )
        
        # Output SES email addresses for configuration
        CfnOutput(
            self,
            "SesEmailAddresses",
            value=",".join(self.config.get("ses", {}).get("email_addresses", [])),
            description="SES email addresses for DMARC report ingestion"
        )
