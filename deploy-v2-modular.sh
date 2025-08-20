#!/bin/bash

# AWS Ops Wheel v2 Modular Deployment Script
# This script deploys the v2 stack using nested CloudFormation templates

set -e  # Exit on any error

# Configuration (default values - will be updated after parsing command line arguments)
SUFFIX=${SUFFIX:-dev}
REGION=${AWS_REGION:-us-west-2}
ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@example.com}

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

# Function to cleanup obsolete build files
cleanup_obsolete_build_files() {
    log_info "Cleaning up obsolete build files..."
    
    # Clean up old Lambda zip files (but keep the ones we just built)
    local lambda_zips_to_clean=()
    
    # Find old zip files that are older than 1 hour (to avoid cleaning recently built ones)
    if command -v find >/dev/null 2>&1; then
        # Use find if available for more precise cleanup
        local old_zips=($(find . -maxdepth 1 -name "*.zip" -type f -mmin +60 2>/dev/null | grep -E "(authorizer_index|index|lambda-layer.*nocrypto)\.zip$" || true))
        lambda_zips_to_clean+=("${old_zips[@]}")
    fi
    
    # Clean up specified files
    for zip_file in "${lambda_zips_to_clean[@]}"; do
        if [[ -f "$zip_file" ]]; then
            log_info "Removing old zip file: $zip_file"
            rm -f "$zip_file"
        fi
    done
    
    # Note: Removed obsolete tenant file cleanup as these files are either:
    # - Still needed (tenant_management.py contains deployment admin functions)
    # - Don't exist (tenant_middleware.py)
    
    # Clean up temporary directories
    if [[ -d "lambda-layer-fixed" ]]; then
        log_info "Removing temporary lambda-layer-fixed directory..."
        rm -rf lambda-layer-fixed
    fi
    
    # Clean up old config files
    local config_files=("config.json" "ui-v2/config.json")
    for config_file in "${config_files[@]}"; do
        if [[ -f "$config_file" ]]; then
            log_info "Removing old config file: $config_file"
            rm -f "$config_file"
        fi
    done
    
    # Clean up old build artifacts in ui-v2
    if [[ -d "ui-v2/build" ]]; then
        log_info "Removing old ui-v2 build directory..."
        rm -rf ui-v2/build
    fi
    
    if [[ -d "ui-v2/dist" ]]; then
        log_info "Removing old ui-v2 dist directory..."
        rm -rf ui-v2/dist
    fi
    
    # Clean up old build directories (keep last 2)
    if [[ -d "build" ]]; then
        log_info "Cleaning up old build directories (keeping last 2)..."
        local old_build_dirs=($(ls -t build/ 2>/dev/null | grep "static_" | tail -n +3 || true))
        
        for dir in "${old_build_dirs[@]}"; do
            if [[ -n "$dir" && -d "build/$dir" ]]; then
                log_info "Removing old build directory: build/$dir"
                rm -rf "build/$dir"
            fi
        done
    fi
    
    # Clean up node_modules/.cache if it exists
    if [[ -d "ui-v2/node_modules/.cache" ]]; then
        log_info "Cleaning up ui-v2 node_modules cache..."
        rm -rf ui-v2/node_modules/.cache
    fi
    
    log_success "Cleanup of obsolete build files completed"
}

# Function to validate security configuration
validate_security_config() {
    log_info "Validating security configuration..."
    
    # Check that admin endpoints are not in PUBLIC_ENDPOINTS in root index.py
    if [ -f "index.py" ]; then
        log_info "Checking index.py for security issues..."
        
        # Check if admin endpoints are incorrectly listed in PUBLIC_ENDPOINTS
        if grep -q "admin.*wheel.*groups.*PUBLIC_ENDPOINTS\|PUBLIC_ENDPOINTS.*admin.*wheel.*groups" "index.py" 2>/dev/null; then
            log_error "SECURITY ISSUE: Admin endpoints found in PUBLIC_ENDPOINTS in index.py"
            log_error "This would bypass authentication for admin endpoints!"
            exit 1
        fi
        
        # More comprehensive check - extract PUBLIC_ENDPOINTS and verify
        local public_endpoints=$(grep -A 10 "PUBLIC_ENDPOINTS.*=" "index.py" | grep -o "'/[^']*'" | tr -d "'" || echo "")
        if echo "$public_endpoints" | grep -q "admin"; then
            log_error "SECURITY ISSUE: Admin endpoint found in PUBLIC_ENDPOINTS in index.py"
            log_error "Found admin endpoints in public list: $(echo "$public_endpoints" | grep admin)"
            exit 1
        fi
        
        log_success "✓ index.py security validation passed"
    else
        log_error "index.py not found!"
        exit 1
    fi
    
    log_success "Security configuration validation completed"
}

# Function to calculate content hash of layer directory
calculate_layer_content_hash() {
    local layer_dir="$1"
    if [ ! -d "$layer_dir" ]; then
        log_error "Layer directory not found: $layer_dir"
        return 1
    fi
    
    # Calculate hash of all files in the layer directory
    # Sort files for consistent ordering across different systems
    local content_hash=$(find "$layer_dir" -type f -exec sha256sum {} \; 2>/dev/null | sort | sha256sum | cut -d' ' -f1)
    echo "$content_hash"
}

# Function to check if layer already exists
check_layer_exists() {
    local layer_name="$1"
    
    # Check if layer exists and get its version
    local layer_info=$(aws lambda get-layer-version \
        --layer-name "$layer_name" \
        --version-number 1 \
        --region "$REGION" 2>/dev/null || echo "")
    
    if [ -n "$layer_info" ]; then
        echo "true"
    else
        echo "false"
    fi
}

# Function to get layer ARN
get_layer_arn() {
    local layer_name="$1"
    local account_id=$(aws sts get-caller-identity --query Account --output text)
    echo "arn:aws:lambda:${REGION}:${account_id}:layer:${layer_name}:1"
}

# Function to cleanup unused layers
cleanup_unused_layers() {
    local days_old=${1:-30}  # Default to 30 days
    
    log_info "Cleaning up unused layer versions older than $days_old days..."
    
    # Get all ops-wheel layers
    local all_layers=$(aws lambda list-layers --region "$REGION" \
        --query 'Layers[?contains(LayerName, `ops-wheel`)].LayerName' \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$all_layers" ]; then
        log_info "No ops-wheel layers found to clean up"
        return 0
    fi
    
    # Get all Lambda functions that use layers
    local functions_with_layers=$(aws lambda list-functions --region "$REGION" \
        --query 'Functions[?contains(FunctionName, `ops-wheel-v2`)].FunctionName' \
        --output text 2>/dev/null || echo "")
    
    local layers_in_use=()
    
    # Check which layers are currently in use
    if [ -n "$functions_with_layers" ]; then
        for func in $functions_with_layers; do
            local func_layers=$(aws lambda get-function --function-name "$func" --region "$REGION" \
                --query 'Configuration.Layers[].Arn' --output text 2>/dev/null || echo "")
            
            if [ -n "$func_layers" ]; then
                for layer_arn in $func_layers; do
                    # Extract layer name from ARN
                    local layer_name=$(echo "$layer_arn" | sed 's/.*:layer:\([^:]*\):.*/\1/')
                    layers_in_use+=("$layer_name")
                done
            fi
        done
    fi
    
    log_info "Found ${#layers_in_use[@]} layers currently in use by Lambda functions"
    
    # Calculate cutoff date (30 days ago)
    local cutoff_date=""
    if command -v date >/dev/null 2>&1; then
        if date --version 2>/dev/null | grep -q GNU; then
            # GNU date
            cutoff_date=$(date -d "$days_old days ago" --iso-8601=seconds)
        else
            # BSD/macOS date
            cutoff_date=$(date -v-${days_old}d -u +"%Y-%m-%dT%H:%M:%S%z")
        fi
    fi
    
    local deleted_count=0
    
    # Check each layer for cleanup
    for layer_name in $all_layers; do
        # Skip if layer is currently in use
        local is_in_use=false
        for used_layer in "${layers_in_use[@]}"; do
            if [ "$layer_name" = "$used_layer" ]; then
                is_in_use=true
                break
            fi
        done
        
        if [ "$is_in_use" = true ]; then
            log_info "Keeping layer (in use): $layer_name"
            continue
        fi
        
        # Get layer versions
        local layer_versions=$(aws lambda list-layer-versions \
            --layer-name "$layer_name" \
            --region "$REGION" \
            --query 'LayerVersions[].[Version,CreatedDate]' \
            --output text 2>/dev/null || echo "")
        
        if [ -n "$layer_versions" ]; then
            while IFS=$'\t' read -r version created_date; do
                # Skip if we can't parse the date or if it's recent
                if [ -n "$cutoff_date" ] && [ -n "$created_date" ]; then
                    if [[ "$created_date" < "$cutoff_date" ]]; then
                        log_info "Deleting old unused layer: $layer_name version $version (created: $created_date)"
                        aws lambda delete-layer-version \
                            --layer-name "$layer_name" \
                            --version-number "$version" \
                            --region "$REGION" >/dev/null 2>&1
                        if [ $? -eq 0 ]; then
                            ((deleted_count++))
                        else
                            log_warning "Failed to delete layer version: $layer_name:$version"
                        fi
                    else
                        log_info "Keeping recent layer: $layer_name version $version (created: $created_date)"
                    fi
                else
                    log_info "Keeping layer (date check skipped): $layer_name version $version"
                fi
            done <<< "$layer_versions"
        fi
    done
    
    if [ $deleted_count -gt 0 ]; then
        log_success "Cleaned up $deleted_count unused layer versions"
    else
        log_info "No unused layer versions found to clean up"
    fi
}

# Function to build and upload Lambda layer with content-hash versioning
build_and_upload_lambda_layer() {
    log_info "Building Lambda layer with content-hash versioning..."
    
    # Step 1: Delete ALL existing lambda layer zip files to ensure fresh build
    log_info "Cleaning up all existing lambda layer zip files..."
    rm -f lambda-layer*.zip
    rm -f lambda-layer-v2*.zip
    log_success "Deleted all existing lambda layer zip files"
    
    # Step 2: Clean up any existing layer directory
    rm -rf lambda-layer-fixed
    mkdir -p lambda-layer-fixed/python
    
    # Step 3: Install minimal Python dependencies first (if requirements exist)
    if [ -f "lambda-layer-requirements.txt" ]; then
        log_info "Installing minimal Python dependencies from lambda-layer-requirements.txt..."
        
        # Check if we have python3 and pip
        if command -v python3 >/dev/null 2>&1 && command -v pip3 >/dev/null 2>&1; then
            log_info "Using python3 and pip3 for dependency installation..."
            pip3 install --target lambda-layer-fixed/python -r lambda-layer-requirements.txt --no-deps --quiet
            log_success "✓ Minimal dependencies installed successfully"
        elif command -v python >/dev/null 2>&1 && command -v pip >/dev/null 2>&1; then
            log_info "Using python and pip for dependency installation..."
            pip install --target lambda-layer-fixed/python -r lambda-layer-requirements.txt --no-deps --quiet
            log_success "✓ Minimal dependencies installed successfully"
        else
            log_warning "Python/pip not found, skipping dependency installation"
            log_info "Layer will only contain application code (Lambda runtime provides boto3/botocore)"
        fi
    else
        log_info "No lambda-layer-requirements.txt found, building layer with code only"
    fi
    
    # Step 4: Copy latest api-v2 code (after synchronization)
    log_info "Copying latest api-v2 code to layer..."
    cp -r api-v2 lambda-layer-fixed/python/
    log_info "Current api-v2 files included in layer:"
    ls -la lambda-layer-fixed/python/api-v2/
    
    # Step 5: Verify the copied code is secure
    log_info "Verifying security of copied code..."
    if grep -q "admin.*PUBLIC_ENDPOINTS\|PUBLIC_ENDPOINTS.*admin" lambda-layer-fixed/python/api-v2/index.py 2>/dev/null; then
        log_error "CRITICAL: Admin endpoints found in PUBLIC_ENDPOINTS in layer code!"
        log_error "Deployment aborted to prevent security breach"
        exit 1
    fi
    log_success "✓ Layer code security verification passed"
    
    # Step 6: Calculate content hash of layer directory
    log_info "Calculating content hash of layer..."
    local content_hash=$(calculate_layer_content_hash "lambda-layer-fixed")
    local short_hash=${content_hash:0:12}  # Use first 12 characters
    
    log_info "Layer content hash: $short_hash"
    
    # Step 7: Generate layer name with content hash
    local layer_name="ops-wheel-v2-deps-${SUFFIX}-${short_hash}"
    
    # Step 8: Check if layer already exists
    log_info "Checking if layer already exists: $layer_name"
    local layer_exists=$(check_layer_exists "$layer_name")
    
    if [ "$layer_exists" = "true" ]; then
        log_success "Layer already exists, reusing: $layer_name"
        local layer_arn=$(get_layer_arn "$layer_name")
        log_info "Using existing layer ARN: $layer_arn"
        
        # Store layer ARN for CloudFormation
        export LAYER_ARN="$layer_arn"
        export LAYER_NAME="$layer_name"
        
        # Still create the zip for backup/debugging purposes
        log_info "Creating backup zip for debugging..."
        cd lambda-layer-fixed
        zip -r "../lambda-layer-${short_hash}.zip" . > /dev/null 2>&1
        cd ..
        
        return 0
    fi
    
    # Step 9: Create new layer since it doesn't exist
    log_info "Creating new layer: $layer_name"
    
    # Show what's in the layer for debugging
    log_info "Layer contents summary:"
    log_info "Total size: $(du -sh lambda-layer-fixed | cut -f1)"
    log_info "Python packages: $(ls lambda-layer-fixed/python/ | grep -v api-v2 | wc -l | tr -d ' ')"
    log_info "API modules: $(ls lambda-layer-fixed/python/api-v2/ | wc -l | tr -d ' ')"
    
    # Create the zip file with content hash
    local layer_zip_name="lambda-layer-${short_hash}.zip"
    
    log_info "Creating layer zip: $layer_zip_name"
    cd lambda-layer-fixed
    zip -r "../$layer_zip_name" . > /dev/null 2>&1
    cd ..
    
    # Create consistent name for CloudFormation and S3 upload
    cp "$layer_zip_name" "lambda-layer-v2.zip"
    
    if [ -f "lambda-layer-v2.zip" ]; then
        local zip_size=$(ls -lh lambda-layer-v2.zip | awk '{print $5}')
        log_info "Layer zip created successfully (size: $zip_size)"
        
        # Upload to S3
        log_info "Uploading Lambda layer to S3..."
        aws s3 cp lambda-layer-v2.zip "s3://$TEMPLATES_BUCKET/lambda-layer-v2.zip" --region $REGION
        
        # Publish new layer version
        log_info "Publishing new layer version: $layer_name"
        local layer_response=$(aws lambda publish-layer-version \
            --layer-name "$layer_name" \
            --description "Content-hash layer for AWS Ops Wheel v2 - Hash: $short_hash" \
            --content S3Bucket="$TEMPLATES_BUCKET",S3Key="lambda-layer-v2.zip" \
            --compatible-runtimes python3.9 \
            --license-info "Apache-2.0" \
            --region "$REGION")
        
        if [ $? -eq 0 ]; then
            # Extract layer ARN from response using AWS CLI query
            local layer_arn=$(echo "$layer_response" | grep -o '"LayerVersionArn": "[^"]*"' | cut -d'"' -f4)
            
            # Fallback: construct ARN manually if extraction failed
            if [ -z "$layer_arn" ]; then
                log_warning "Could not extract LayerVersionArn from API response, constructing manually"
                layer_arn=$(get_layer_arn "$layer_name")
            fi
            
            # Validate layer ARN format (fix hyphen position in regex)
            if [[ ! "$layer_arn" =~ ^arn:aws:lambda:[a-z0-9-]+:[0-9]+:layer:[a-zA-Z0-9_-]+:[0-9]+$ ]]; then
                log_error "Invalid layer ARN format: $layer_arn"
                log_error "Expected format: arn:aws:lambda:region:account:layer:name:version"
                log_error "ARN length: ${#layer_arn} characters"
                log_error "Debug - ARN breakdown:"
                log_error "  Full ARN: '$layer_arn'"
                log_error "  Ends with digit: $(echo "$layer_arn" | grep -o '[0-9]$' || echo 'NO')"
                exit 1
            fi
            
            log_success "Lambda layer created successfully: $layer_name"
            log_info "Layer ARN: $layer_arn"
            
            # Verify layer actually exists before proceeding
            log_info "Verifying layer exists..."
            local verify_response=$(aws lambda get-layer-version-by-arn \
                --arn "$layer_arn" \
                --region "$REGION" 2>/dev/null || echo "")
            
            if [ -z "$verify_response" ]; then
                log_error "Failed to verify layer exists: $layer_arn"
                exit 1
            fi
            log_success "✓ Layer verified and accessible"
            
            # Store layer ARN for CloudFormation
            export LAYER_ARN="$layer_arn"
            export LAYER_NAME="$layer_name"
            
            # Add git commit info if available
            if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
                local git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
                log_info "Git commit: $git_commit"
            fi
            
            # Keep the hash-named version for debugging
            log_info "Backup layer saved as: $layer_zip_name"
        else
            log_error "Failed to publish Lambda layer version"
            exit 1
        fi
    else
        log_error "Failed to create Lambda layer zip file"
        exit 1
    fi
}

# Function to build and upload Lambda function zip files
build_and_upload_lambda_functions() {
    log_info "Building and uploading Lambda function zip files..."
    
    # Step 1: Delete ALL existing Lambda function zip files for fresh build
    log_info "Cleaning up all existing Lambda function zip files..."
    rm -f index.zip
    rm -f authorizer_index.zip
    rm -f lambda_function.zip
    log_success "Deleted all existing Lambda function zip files"
    
    # Step 2: Build index.zip from current root index.py (no unnecessary copying)
    if [ -f "index.py" ]; then
        log_info "Building fresh index.zip from root index.py with latest routing logic..."
        zip index.zip index.py > /dev/null 2>&1
        log_success "Built fresh index.zip with latest code"
    else
        log_error "No index.py found to build Lambda function"
        exit 1
    fi
    
    # Step 3: Build authorizer_index.zip if source exists
    if [ -f "authorizer_index.py" ]; then
        log_info "Building fresh authorizer_index.zip..."
        zip authorizer_index.zip authorizer_index.py > /dev/null 2>&1
        log_success "Built fresh authorizer_index.zip"
    else
        log_warning "authorizer_index.py not found, skipping authorizer build"
    fi
    
    # Step 4: Upload all function zip files
    local zip_files=(
        "index.zip"
        "authorizer_index.zip"
    )
    
    for zip_file in "${zip_files[@]}"; do
        if [ -f "$zip_file" ]; then
            log_info "Uploading $zip_file to S3..."
            aws s3 cp "$zip_file" "s3://$TEMPLATES_BUCKET/$zip_file" --region $REGION
            log_success "Uploaded $zip_file"
        else
            log_warning "Lambda function zip file not found, skipping: $zip_file"
        fi
    done
    
    log_success "All Lambda function zip files built and uploaded successfully"
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

# Function to force API Gateway deployment
force_api_gateway_deployment() {
    log_info "Forcing API Gateway deployment to apply authentication configuration..."
    
    # Get API Gateway ID from stack outputs
    local api_gateway_id=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayId`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$api_gateway_id" ] && [ "$api_gateway_id" != "None" ]; then
        log_info "Creating new API Gateway deployment for API: $api_gateway_id"
        aws apigateway create-deployment \
            --rest-api-id "$api_gateway_id" \
            --stage-name "$SUFFIX" \
            --description "Force deployment to apply authentication configuration - $(date)" \
            --region $REGION > /dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            log_success "✓ API Gateway deployment created - authentication configuration applied"
        else
            log_warning "API Gateway deployment may have failed, but continuing..."
        fi
    else
        log_warning "Could not determine API Gateway ID from stack outputs"
        log_info "This may be normal if the stack is not fully deployed yet"
    fi
}

# Function to deploy the main stack
deploy_stack() {
    log_info "Deploying main orchestrator stack: $STACK_NAME"
    
    # Use content-hash based layer ARN instead of timestamp versioning
    if [ -z "$LAYER_ARN" ] || [ -z "$LAYER_NAME" ]; then
        log_error "Layer ARN or Layer Name not set. build_and_upload_lambda_layer must be called first."
        exit 1
    fi
    
    # Validate layer ARN format before CloudFormation deployment
    if [[ ! "$LAYER_ARN" =~ ^arn:aws:lambda:[a-z0-9-]+:[0-9]+:layer:[a-zA-Z0-9_-]+:[0-9]+$ ]]; then
        log_error "Invalid layer ARN format before CloudFormation deployment: $LAYER_ARN"
        log_error "Expected format: arn:aws:lambda:region:account:layer:name:version"
        log_error "ARN length: ${#LAYER_ARN} characters"
        log_error "Debug - ARN breakdown:"
        log_error "  Full ARN: '$LAYER_ARN'"
        log_error "  Ends with digit: $(echo "$LAYER_ARN" | grep -o '[0-9]$' || echo 'NO')"
        log_error "This would cause CloudFormation deployment to fail with validation error"
        exit 1
    fi
    
    log_info "Using content-hash based layer: $LAYER_NAME"
    log_info "Layer ARN: $LAYER_ARN"
    log_success "✓ Layer ARN format validated for CloudFormation"
    
    # Force Lambda container refresh by updating configuration after deployment
    force_lambda_container_refresh() {
        local function_name=$1
        log_info "Forcing Lambda container refresh for: $function_name"
        
        # Get current configuration using AWS CLI queries (more reliable than JSON parsing)
        local current_timeout=$(aws lambda get-function-configuration \
            --function-name "$function_name" \
            --region "$REGION" \
            --query 'Timeout' \
            --output text 2>/dev/null || echo "30")
        
        local current_memory=$(aws lambda get-function-configuration \
            --function-name "$function_name" \
            --region "$REGION" \
            --query 'MemorySize' \
            --output text 2>/dev/null || echo "256")
        
        # Validate we got valid numbers
        if ! [[ "$current_timeout" =~ ^[0-9]+$ ]]; then
            log_warning "Could not retrieve valid timeout for $function_name, using default 30"
            current_timeout=30
        fi
        
        if ! [[ "$current_memory" =~ ^[0-9]+$ ]]; then
            log_warning "Could not retrieve valid memory size for $function_name, using default 256"
            current_memory=256
        fi
        
        log_info "Current configuration - Timeout: ${current_timeout}s, Memory: ${current_memory}MB"
        
        # Method 1: Update timeout to force container restart
        log_info "Updating timeout to force all containers to restart..."
        aws lambda update-function-configuration \
            --function-name "$function_name" \
            --timeout $((current_timeout + 1)) \
            --description "Force container refresh - $(date)" \
            --region "$REGION" >/dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            log_success "✓ Timeout updated successfully"
        else
            log_warning "Failed to update timeout, but continuing..."
        fi
        
        # Wait for update to complete
        sleep 3
        
        # Method 2: Also update memory by 1MB to ensure all containers are destroyed
        log_info "Updating memory to ensure complete container refresh..."
        aws lambda update-function-configuration \
            --function-name "$function_name" \
            --memory-size $((current_memory + 1)) \
            --region "$REGION" >/dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            log_success "✓ Memory updated successfully"
        else
            log_warning "Failed to update memory, but continuing..."
        fi
        
        # Wait for update to complete
        sleep 3
        
        # Reset to original configuration
        log_info "Resetting to original configuration..."
        aws lambda update-function-configuration \
            --function-name "$function_name" \
            --timeout "$current_timeout" \
            --memory-size "$current_memory" \
            --description "Configuration reset after container refresh" \
            --region "$REGION" >/dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            log_success "✓ Configuration reset successfully"
        else
            log_warning "Failed to reset configuration, but container refresh was still effective"
        fi
        
        # Wait for final update to complete
        sleep 2
        
        log_success "✓ Container refresh completed for $function_name"
    }
    
    local parameters=(
        "ParameterKey=Environment,ParameterValue=$SUFFIX"
        "ParameterKey=AdminEmail,ParameterValue=$ADMIN_EMAIL"
        "ParameterKey=TemplatesBucketName,ParameterValue=$TEMPLATES_BUCKET"
        "ParameterKey=LayerArn,ParameterValue=$LAYER_ARN"
    )
    
    # Check if stack exists with more robust detection
    log_info "Checking if stack exists: $STACK_NAME"
    local stack_status=""
    local stack_exists=false
    
    # Try to get stack status
    stack_status=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].StackStatus' \
        --output text 2>/dev/null || echo "DOES_NOT_EXIST")
    
    if [ "$stack_status" != "DOES_NOT_EXIST" ] && [ -n "$stack_status" ]; then
        stack_exists=true
        log_info "Stack found with status: $stack_status"
    else
        log_info "Stack does not exist"
    fi
    
    if [ "$stack_exists" = true ]; then
        # Check if stack is in a failed state that requires deletion
        case "$stack_status" in
            "CREATE_FAILED"|"ROLLBACK_COMPLETE"|"DELETE_FAILED")
                log_warning "Stack is in failed state: $stack_status"
                log_warning "This stack needs to be deleted manually before deployment can proceed"
                log_error "Please delete the stack manually: aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
                exit 1
                ;;
            "DELETE_IN_PROGRESS")
                log_warning "Stack is currently being deleted. Please wait for deletion to complete."
                exit 1
                ;;
            *)
                log_info "Stack exists and is in valid state for update: $stack_status"
                log_info "Updating existing stack..."
                aws cloudformation update-stack \
                    --stack-name "$STACK_NAME" \
                    --template-body file://cloudformation-v2/awsopswheel-v2.yml \
                    --parameters "${parameters[@]}" \
                    --capabilities CAPABILITY_NAMED_IAM \
                    --region $REGION
                
                log_info "Waiting for stack update to complete..."
                aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME" --region $REGION
                log_success "Stack update completed successfully"
                
                # Force Lambda container refresh to ensure no stale containers
                log_info "Forcing Lambda container refresh to eliminate stale containers..."
                force_lambda_container_refresh "ops-wheel-v2-tenant-management-${SUFFIX}"
                log_success "Lambda containers refreshed"
                ;;
        esac
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

# Function to create deployment admin user
create_deployment_admin_user() {
    log_info "Managing deployment admin user..."
    
    # Get User Pool ID from stack outputs
    local user_pool_id=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
        --output text)
    
    if [ -z "$user_pool_id" ] || [ "$user_pool_id" = "None" ]; then
        log_error "Could not determine User Pool ID"
        return 1
    fi
    
    local temp_password="TempPass123!${SUFFIX}"
    
    # Determine if admin email/username were explicitly provided (not defaults)
    local admin_email_provided=false
    local admin_username_provided=false
    
    # Check if ADMIN_EMAIL was explicitly set (not default)
    if [ "$ADMIN_EMAIL" != "admin@example.com" ]; then
        admin_email_provided=true
    fi
    
    # Check if ADMIN_USERNAME was explicitly set (not default)  
    if [ "$ADMIN_USERNAME" != "admin" ]; then
        admin_username_provided=true
    fi
    
    # Use custom username if different from email
    local admin_username="$ADMIN_USERNAME"
    if [ "$admin_username" = "admin" ] && [ "$ADMIN_EMAIL" != "admin@example.com" ]; then
        # If email was customized but username wasn't, extract username from email
        admin_username=$(echo "$ADMIN_EMAIL" | cut -d'@' -f1)
        log_info "Auto-generated username from email: $admin_username"
    fi
    
    # Check if user already exists (check both username and email)
    local existing_user=""
    local existing_user_info=""
    
    if aws cognito-idp admin-get-user \
        --user-pool-id "$user_pool_id" \
        --username "$admin_username" \
        --region $REGION > /dev/null 2>&1; then
        existing_user="$admin_username"
        existing_user_info=$(aws cognito-idp admin-get-user \
            --user-pool-id "$user_pool_id" \
            --username "$admin_username" \
            --region $REGION 2>/dev/null)
    elif aws cognito-idp admin-get-user \
        --user-pool-id "$user_pool_id" \
        --username "$ADMIN_EMAIL" \
        --region $REGION > /dev/null 2>&1; then
        existing_user="$ADMIN_EMAIL"
        existing_user_info=$(aws cognito-idp admin-get-user \
            --user-pool-id "$user_pool_id" \
            --username "$ADMIN_EMAIL" \
            --region $REGION 2>/dev/null)
    fi
    
    if [ -n "$existing_user" ]; then
        log_success "Deployment admin user already exists: $existing_user"
        
        # Get current email from existing user
        local current_email=""
        if [ -n "$existing_user_info" ]; then
            current_email=$(echo "$existing_user_info" | grep -A1 '"Name": "email"' | grep '"Value"' | sed 's/.*"Value": "\([^"]*\)".*/\1/' || echo "")
        fi
        
        # Only update attributes if new values were explicitly provided
        local update_needed=false
        local update_attributes=()
        
        if [ "$admin_email_provided" = true ] && [ "$current_email" != "$ADMIN_EMAIL" ]; then
            log_info "Email explicitly provided and different from current: $current_email -> $ADMIN_EMAIL"
            update_attributes+=("Name=email,Value=$ADMIN_EMAIL")
            update_attributes+=("Name=email_verified,Value=true")
            update_needed=true
        fi
        
        # Always ensure deployment_admin flag is set (safe to update)
        update_attributes+=("Name=custom:deployment_admin,Value=true")
        update_needed=true
        
        if [ "$update_needed" = true ]; then
            log_info "Updating deployment admin attributes..."
            aws cognito-idp admin-update-user-attributes \
                --user-pool-id "$user_pool_id" \
                --username "$existing_user" \
                --user-attributes "${update_attributes[@]}" \
                --region $REGION
            
            log_success "Updated deployment admin user attributes"
        else
            log_info "No updates needed for existing deployment admin user"
        fi
        
        # Use existing user's email for display if no new email provided
        if [ "$admin_email_provided" = false ] && [ -n "$current_email" ]; then
            ADMIN_EMAIL="$current_email"
            log_info "Preserving existing admin email: $current_email"
        fi
    else
        # Create new user
        log_info "Creating new deployment admin user: $admin_username ($ADMIN_EMAIL)"
        
        aws cognito-idp admin-create-user \
            --user-pool-id "$user_pool_id" \
            --username "$admin_username" \
            --user-attributes \
                Name=email,Value="$ADMIN_EMAIL" \
                Name=email_verified,Value=true \
                Name=custom:deployment_admin,Value=true \
            --temporary-password "$temp_password" \
            --message-action SUPPRESS \
            --region $REGION
        
        if [ $? -eq 0 ]; then
            log_success "Created deployment admin user successfully"
        else
            log_error "Failed to create deployment admin user"
            return 1
        fi
    fi
    
    # Store final credentials for display
    FINAL_ADMIN_USERNAME="$admin_username"
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
        # Step 1: Clean all existing build artifacts first
        log_info "Cleaning up all existing frontend build artifacts..."
        rm -rf ui-v2/build
        rm -rf ui-v2/dist  
        rm -rf ui-v2/.next
        rm -rf ui-v2/out
        rm -rf build/static*
        rm -rf build
        rm -f config.json
        log_success "Deleted all existing frontend build artifacts"
        
        # Step 2: Clean npm cache for fresh dependencies
        log_info "Cleaning npm cache for fresh build..."
        cd ui-v2
        if [ -d "node_modules/.cache" ]; then
            rm -rf node_modules/.cache
            log_success "Cleared npm cache"
        fi
        
        # Step 3: Install dependencies and build
        if [ -f "package.json" ]; then
            log_info "Installing fresh npm dependencies..."
            npm install
            
            log_info "Building fresh frontend with latest code..."
            npm run build
            log_success "Built fresh frontend successfully"
            
            # Step 4: Create fallback index.html file for CloudFront default root object
            if [ -f "../build/static/index.production.html" ]; then
                cp ../build/static/index.production.html ../build/static/index.html
                log_info "Created fallback index.html file"
            fi
            
            # Step 5: Get frontend bucket and upload
            local bucket_name=$(aws cloudformation describe-stacks \
                --stack-name "$STACK_NAME" \
                --region $REGION \
                --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
                --output text)
            
            if [ -n "$bucket_name" ] && [ "$bucket_name" != "None" ]; then
                log_info "Uploading fresh frontend build to S3 bucket: $bucket_name"
                aws s3 sync ../build/static/ "s3://$bucket_name/app/" --delete --exclude "config.json" --region $REGION
                log_success "Uploaded fresh frontend build to S3"
                
                # Step 6: Invalidate CloudFront cache to serve fresh content
                local distribution_id=$(aws cloudformation describe-stacks \
                    --stack-name "$STACK_NAME" \
                    --region $REGION \
                    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
                    --output text 2>/dev/null || echo "")
                
                if [ -n "$distribution_id" ] && [ "$distribution_id" != "None" ]; then
                    log_info "Invalidating CloudFront cache for fresh content delivery..."
                    aws cloudfront create-invalidation \
                        --distribution-id "$distribution_id" \
                        --paths "/*" > /dev/null
                    log_success "CloudFront cache invalidated - fresh content will be served"
                fi
                
                log_success "Frontend deployment completed successfully"
            else
                log_warning "Could not determine frontend bucket name for upload"
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
    log_info "Suffix: $SUFFIX"
    log_info "Region: $REGION"
    log_info "Stack Name: $STACK_NAME"
    log_info "Admin Email: $ADMIN_EMAIL"
    log_info "Templates Bucket: $TEMPLATES_BUCKET"
    echo
    
    # Set trap to cleanup on error
    trap cleanup_on_error ERR
    
    # Execute deployment steps
    check_aws_config
    cleanup_obsolete_build_files  # Clean up before starting
    validate_security_config      # NEW: Validate security before deployment
    create_templates_bucket
    validate_templates
    upload_templates
    build_and_upload_lambda_layer
    build_and_upload_lambda_functions
    deploy_stack
    force_api_gateway_deployment  # NEW: Force API Gateway to apply auth config
    show_outputs
    create_deployment_admin_user
    create_and_upload_config
    build_and_upload_frontend
    cleanup_obsolete_build_files  # Clean up after deployment
    cleanup_unused_layers         # Clean up old unused layer versions
    
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
    
    log_info "=== Deployment Admin Credentials ==="
    log_success "Username: ${FINAL_ADMIN_USERNAME:-$ADMIN_USERNAME}"
    log_success "Email: $ADMIN_EMAIL"
    log_success "Temporary Password: TempPass123!${SUFFIX}"
    log_warning "⚠️  IMPORTANT: You will be prompted to change this password on first login"
    log_warning "⚠️  The deployment admin will see the admin dashboard automatically after login"
    echo
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --suffix|-s)
            SUFFIX="$2"
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
        --admin-username)
            ADMIN_USERNAME="$2"
            shift 2
            ;;
        --help|-h)
            echo "AWS Ops Wheel v2 Modular Deployment Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -s, --suffix SUFFIX       Deployment suffix (e.g., dev, staging, prod, mybranch) [default: dev]"
            echo "  -r, --region REGION       AWS region [default: us-west-2]"
            echo "  --admin-email EMAIL       Admin email address [default: admin@example.com]"
            echo "  --admin-username USER     Admin username [default: admin or auto-generated from email]"
            echo "  -h, --help               Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  SUFFIX                    Same as --suffix"
            echo "  AWS_REGION               Same as --region"
            echo "  ADMIN_EMAIL              Same as --admin-email"
            echo "  ADMIN_USERNAME           Same as --admin-username"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set derived configuration variables after parsing command line arguments
STACK_NAME="aws-ops-wheel-v2-${SUFFIX}"
TEMPLATES_BUCKET="ops-wheel-v2-deployment-${SUFFIX}-${REGION}"

# Run main function
main
