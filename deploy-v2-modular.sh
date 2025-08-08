#!/bin/bash

# AWS Ops Wheel v2 Modular Deployment Script
# This script deploys the v2 stack using nested CloudFormation templates

set -e  # Exit on any error

# Configuration
ENVIRONMENT=${ENVIRONMENT:-dev}
REGION=${AWS_REGION:-us-west-2}
STACK_NAME="aws-ops-wheel-v2-${ENVIRONMENT}"
TEMPLATES_BUCKET="ops-wheel-v2-deployment-${ENVIRONMENT}-${REGION}"
LAMBDA_LAYER_BUCKET_PATTERN="ops-wheel-v2-layer-${ENVIRONMENT}-${REGION}"
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@example.com}
TENANT_DOMAIN=${TENANT_DOMAIN:-example.com}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if AWS CLI is configured
check_aws_config() {
    log_info "Checking AWS CLI configuration..."
    
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        log_error "AWS CLI is not configured properly. Please run 'aws configure'"
        exit 1
    fi
    
    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local current_region=$(aws configure get region)
    
    log_success "AWS CLI configured for account: $account_id, region: $current_region"
    
    if [ "$current_region" != "$REGION" ]; then
        log_warning "Current AWS region ($current_region) differs from script region ($REGION)"
        log_warning "Using region: $REGION"
    fi
}

# Function to create S3 bucket for templates
create_templates_bucket() {
    log_info "Creating/checking S3 bucket for templates: $TEMPLATES_BUCKET"
    
    if aws s3 ls "s3://$TEMPLATES_BUCKET" > /dev/null 2>&1; then
        log_success "Templates bucket already exists: $TEMPLATES_BUCKET"
    else
        log_info "Creating templates bucket: $TEMPLATES_BUCKET"
        if [ "$REGION" = "us-east-1" ]; then
            aws s3api create-bucket --bucket "$TEMPLATES_BUCKET" --region $REGION
        else
            aws s3api create-bucket --bucket "$TEMPLATES_BUCKET" --region $REGION --create-bucket-configuration LocationConstraint=$REGION
        fi
        log_success "Created templates bucket: $TEMPLATES_BUCKET"
    fi
}

# Function to upload CloudFormation templates
upload_templates() {
    log_info "Uploading CloudFormation templates to S3..."
    
    local templates=(
        "dynamodb-v2.yml"
        "cognito-v2.yml" 
        "lambda-v2.yml"
        "api-gateway-v2.yml"
        "frontend-v2.yml"
    )
    
    for template in "${templates[@]}"; do
        if [ -f "cloudformation-v2/$template" ]; then
            log_info "Uploading $template..."
            aws s3 cp "cloudformation-v2/$template" "s3://$TEMPLATES_BUCKET/templates/$template" --region $REGION
            log_success "Uploaded $template"
        else
            log_error "Template not found: cloudformation-v2/$template"
            exit 1
        fi
    done
    
    log_success "All templates uploaded successfully"
}

# Function to build and upload Lambda layer
build_and_upload_lambda_layer() {
    log_info "Building Lambda layer with latest code..."
    
    # Always rebuild the layer to ensure latest code
    rm -rf lambda-layer-fixed
    mkdir -p lambda-layer-fixed/python
    cp -r api-v2 lambda-layer-fixed/python/
    
    # Create the zip file
    cd lambda-layer-fixed
    zip -r ../lambda-layer-v2-fixed-nocrypto.zip . > /dev/null 2>&1
    cd ..
    
    if [ -f "lambda-layer-v2-fixed-nocrypto.zip" ]; then
        log_info "Uploading Lambda layer..."
        aws s3 cp lambda-layer-v2-fixed-nocrypto.zip "s3://$TEMPLATES_BUCKET/lambda-layer-v2-fixed-nocrypto.zip" --region $REGION
        log_success "Lambda layer uploaded with latest code"
    else
        log_error "Failed to create Lambda layer zip file"
        exit 1
    fi
}

# Function to validate templates
validate_templates() {
    log_info "Validating CloudFormation templates..."
    
    local templates=(
        "dynamodb-v2.yml"
        "cognito-v2.yml" 
        "lambda-v2.yml"
        "api-gateway-v2.yml"
        "frontend-v2.yml"
        "awsopswheel-v2.yml"
    )
    
    for template in "${templates[@]}"; do
        if [ -f "cloudformation-v2/$template" ]; then
            log_info "Validating $template..."
            if aws cloudformation validate-template --template-body "file://cloudformation-v2/$template" --region $REGION > /dev/null; then
                log_success "✓ $template is valid"
            else
                log_error "✗ $template validation failed"
                exit 1
            fi
        fi
    done
}

# Function to deploy the main stack
deploy_stack() {
    log_info "Deploying main orchestrator stack: $STACK_NAME"
    
    # Generate timestamp-based layer version to force CloudFormation to update layer
    local layer_version=$(date +%s)
    log_info "Using LayerVersion: $layer_version (timestamp-based)"
    
    local parameters=(
        "ParameterKey=Environment,ParameterValue=$ENVIRONMENT"
        "ParameterKey=AdminEmail,ParameterValue=$ADMIN_EMAIL"
        "ParameterKey=TenantDomain,ParameterValue=$TENANT_DOMAIN"
        "ParameterKey=TemplatesBucketName,ParameterValue=$TEMPLATES_BUCKET"
        "ParameterKey=LayerVersion,ParameterValue=$layer_version"
    )
    
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region $REGION > /dev/null 2>&1; then
        log_info "Stack exists, updating..."
        aws cloudformation update-stack \
            --stack-name "$STACK_NAME" \
            --template-body file://cloudformation-v2/awsopswheel-v2.yml \
            --parameters "${parameters[@]}" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region $REGION
        
        log_info "Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME" --region $REGION
        log_success "Stack update completed successfully"
    else
        log_info "Creating new stack..."
        aws cloudformation create-stack \
            --stack-name "$STACK_NAME" \
            --template-body file://cloudformation-v2/awsopswheel-v2.yml \
            --parameters "${parameters[@]}" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region $REGION
        
        log_info "Waiting for stack creation to complete..."
        aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME" --region $REGION
        log_success "Stack creation completed successfully"
    fi
}

# Function to display stack outputs
show_outputs() {
    log_info "Retrieving stack outputs..."
    
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`ApplicationInfo` || OutputKey==`DeploymentInstructions`].[OutputKey,OutputValue]' \
        --output table
}

# Function to create and upload config.json
create_and_upload_config() {
    log_info "Creating frontend configuration..."
    
    # Get stack outputs
    local cognito_user_pool_id=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
        --output text)
    
    local cognito_client_id=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
        --output text)
    
    local api_url=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayURL`].OutputValue' \
        --output text)
    
    local bucket_name=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
        --output text)
    
    if [ -z "$cognito_user_pool_id" ] || [ -z "$cognito_client_id" ] || [ -z "$api_url" ]; then
        log_error "Failed to retrieve required stack outputs for config.json"
        log_error "UserPoolId: $cognito_user_pool_id"
        log_error "ClientId: $cognito_client_id"
        log_error "ApiUrl: $api_url"
        return 1
    fi
    
    # Create config.json with field names that match frontend expectations
    cat > config.json << EOF
{
  "UserPoolId": "$cognito_user_pool_id",
  "ClientId": "$cognito_client_id",
  "API_BASE_URL": "$api_url/app/api/v2",
  "REGION": "$REGION"
}
EOF
    
    log_success "Created config.json with application configuration"
    
    # Upload config.json to S3
    if [ -n "$bucket_name" ] && [ "$bucket_name" != "None" ]; then
        log_info "Uploading config.json to bucket: $bucket_name"
        aws s3 cp config.json "s3://$bucket_name/app/config.json" --region $REGION
        log_success "Configuration file uploaded successfully"
    else
        log_warning "Could not determine frontend bucket name for config upload"
    fi
}

# Function to build and upload frontend
build_and_upload_frontend() {
    log_info "Building and uploading frontend..."
    
    if [ -d "ui-v2" ]; then
        log_info "Building frontend..."
        cd ui-v2
        if [ -f "package.json" ]; then
            npm install
            npm run build
            
            # Create fallback index.html file for CloudFront default root object
            if [ -f "../build/static/index.production.html" ]; then
                cp ../build/static/index.production.html ../build/static/index.html
                log_info "Created fallback index.html file"
            fi
            
            # Get frontend bucket from stack outputs
            local bucket_name=$(aws cloudformation describe-stacks \
                --stack-name "$STACK_NAME" \
                --region $REGION \
                --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
                --output text)
            
            if [ -n "$bucket_name" ] && [ "$bucket_name" != "None" ]; then
                log_info "Uploading frontend to bucket: $bucket_name"
                aws s3 sync ../build/static/ "s3://$bucket_name/app/" --delete --exclude "config.json" --region $REGION
                
                # Get CloudFront distribution ID and invalidate cache
                local distribution_id=$(aws cloudformation describe-stacks \
                    --stack-name "$STACK_NAME" \
                    --region $REGION \
                    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
                    --output text 2>/dev/null || echo "")
                
                if [ -n "$distribution_id" ] && [ "$distribution_id" != "None" ]; then
                    log_info "Creating CloudFront invalidation..."
                    aws cloudfront create-invalidation \
                        --distribution-id "$distribution_id" \
                        --paths "/*" > /dev/null
                    log_success "CloudFront cache invalidated"
                fi
                
                log_success "Frontend uploaded successfully"
            else
                log_warning "Could not determine frontend bucket name"
            fi
        else
            log_warning "No package.json found in ui-v2 directory"
        fi
        cd ..
    else
        log_warning "ui-v2 directory not found, skipping frontend build"
    fi
}

# Function to cleanup on error
cleanup_on_error() {
    log_error "Deployment failed! Check the CloudFormation console for details."
    log_info "Stack events: https://console.aws.amazon.com/cloudformation/home?region=$REGION#/stacks/events?stackId=$STACK_NAME"
}

# Main execution
main() {
    log_info "Starting AWS Ops Wheel v2 Modular Deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Region: $REGION"
    log_info "Stack Name: $STACK_NAME"
    log_info "Admin Email: $ADMIN_EMAIL"
    log_info "Templates Bucket: $TEMPLATES_BUCKET"
    echo
    
    # Set trap to cleanup on error
    trap cleanup_on_error ERR
    
    # Execute deployment steps
    check_aws_config
    create_templates_bucket
    validate_templates
    upload_templates
    build_and_upload_lambda_layer
    deploy_stack
    show_outputs
    create_and_upload_config
    build_and_upload_frontend
    
    log_success "🎉 AWS Ops Wheel v2 deployment completed successfully!"
    
    # Show final URLs
    echo
    log_info "=== Application URLs ==="
    local frontend_url=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`FrontendURL`].OutputValue' \
        --output text)
    
    local api_url=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayURL`].OutputValue' \
        --output text)
    
    log_success "Frontend: $frontend_url"
    log_success "API: $api_url"
    echo
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment|-e)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --region|-r)
            REGION="$2"
            shift 2
            ;;
        --admin-email)
            ADMIN_EMAIL="$2"
            shift 2
            ;;
        --tenant-domain)
            TENANT_DOMAIN="$2"
            shift 2
            ;;
        --help|-h)
            echo "AWS Ops Wheel v2 Modular Deployment Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV     Environment (dev/staging/prod) [default: dev]"
            echo "  -r, --region REGION       AWS region [default: us-west-2]"
            echo "  --admin-email EMAIL       Admin email address [default: admin@example.com]"
            echo "  --tenant-domain DOMAIN    Primary tenant domain [default: example.com]"
            echo "  -h, --help               Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  ENVIRONMENT               Same as --environment"
            echo "  AWS_REGION               Same as --region"
            echo "  ADMIN_EMAIL              Same as --admin-email"
            echo "  TENANT_DOMAIN            Same as --tenant-domain"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main
