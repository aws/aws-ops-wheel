#!/bin/bash

# AWS Ops Wheel Streamlined Deployment Script
# This script automates the entire deployment process

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

log_header() {
    echo
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}================================================================${NC}"
}

# Default values
EMAIL=""
SUFFIX=""
REGION="us-west-2"
UPDATE_ONLY=false
CLEANUP_LOCAL=true
CLEANUP_S3=false
KEEP_COUNT=2
DELETE_STACKS=false

# Function to show usage
show_usage() {
    cat << EOF
AWS Ops Wheel Streamlined Deployment Script

Usage: $0 [OPTIONS]

OPTIONS:
    -e, --email EMAIL       Email address (required for initial deployment)
    -s, --suffix SUFFIX     Stack suffix (optional)
    -r, --region REGION     AWS region (default: us-west-2)
    --update-only          Only update app (skip infrastructure)
    --cleanup-s3           Clean up old S3 static directories (keeps last 2)
    --no-cleanup-local      Skip cleanup of local static directories  
    --keep-count N         Number of static directories to keep (default: 2)
    --delete               Delete all stacks (empties S3 bucket automatically)
    -h, --help             Show this help message

EXAMPLES:
    # Full initial deployment (includes CloudFront)
    $0 --email your@email.com

    # Deploy with suffix
    $0 --email your@email.com --suffix dev

    # Update app only (after initial deployment)
    $0 --update-only

    # Deploy with S3 cleanup (removes old static dirs from S3)
    $0 --update-only --cleanup-s3

    # Deploy keeping more old directories
    $0 --update-only --keep-count 5

    # Delete all stacks
    $0 --delete
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--email)
            EMAIL="$2"
            shift 2
            ;;
        -s|--suffix)
            SUFFIX="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        --update-only)
            UPDATE_ONLY=true
            shift
            ;;
        --cleanup-s3)
            CLEANUP_S3=true
            shift
            ;;
        --no-cleanup-local)
            CLEANUP_LOCAL=false
            shift
            ;;
        --keep-count)
            KEEP_COUNT="$2"
            shift 2
            ;;
        --delete)
            DELETE_STACKS=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Set stack names
if [[ -n "$SUFFIX" ]]; then
    MAIN_STACK="AWSOpsWheel-$SUFFIX"
    CLOUDFRONT_STACK="AWSOpsWheel-$SUFFIX-CloudFront"
else
    MAIN_STACK="AWSOpsWheel"
    CLOUDFRONT_STACK="AWSOpsWheel-CloudFront"
fi

SOURCE_BUCKET_STACK="AWSOpsWheelSourceBucket"

# Function to check if stack exists
stack_exists() {
    local stack_name=$1
    aws cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" >/dev/null 2>&1
}

# Function to wait for stack operation
wait_for_stack() {
    local stack_name=$1
    local operation=$2
    log_info "Waiting for stack $operation to complete: $stack_name"
    aws cloudformation wait "stack-$operation-complete" --stack-name "$stack_name" --region "$REGION"
}

# Function to get stack output
get_stack_output() {
    local stack_name=$1
    local output_key=$2
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text \
        --region "$REGION"
}

# Function to get most recent static directory
get_latest_static_dir() {
    ls -t build/ | grep "static_" | head -1
}

# Function to cleanup old static directories (keep last N)
cleanup_old_static_dirs() {
    local keep_count=${1:-2}  # Keep last N directories (default: 2)
    local location=${2:-"local"}  # "local" or "s3"
    
    if [[ "$location" == "local" ]]; then
        log_info "Cleaning up old local static directories (keeping last $keep_count)..."
        local old_dirs=($(ls -t build/ | grep "static_" | tail -n +$((keep_count + 1))))
        
        for dir in "${old_dirs[@]}"; do
            if [[ -n "$dir" ]]; then
                log_info "Removing old local directory: build/$dir"
                rm -rf "build/$dir"
            fi
        done
    elif [[ "$location" == "s3" ]]; then
        log_info "Cleaning up old S3 static directories (keeping last $keep_count)..."
        local s3_dirs=($(aws s3 ls "s3://$S3_BUCKET/" | grep "static_" | awk '{print $2}' | sed 's|/||' | sort -r | tail -n +$((keep_count + 1))))
        
        for dir in "${s3_dirs[@]}"; do
            if [[ -n "$dir" ]]; then
                log_info "Removing old S3 directory: s3://$S3_BUCKET/$dir/"
                aws s3 rm "s3://$S3_BUCKET/$dir/" --recursive --region "$REGION"
            fi
        done
    fi
}

# Function to deploy main application
deploy_main_app() {
    log_header "DEPLOYING MAIN APPLICATION"
    
    if [[ -z "$EMAIL" ]] && ! stack_exists "$MAIN_STACK"; then
        log_error "Email is required for initial deployment"
        exit 1
    fi
    
    local suffix_arg=""
    if [[ -n "$SUFFIX" ]]; then
        suffix_arg="--suffix $SUFFIX"
    fi
    
    local email_arg=""
    if [[ -n "$EMAIL" ]]; then
        email_arg="--email $EMAIL"
    fi
    
    log_info "Building and deploying main application..."
    ./run $suffix_arg $email_arg
    
    log_success "Main application deployed successfully"
}

# Function to get infrastructure IDs
get_infrastructure_ids() {
    log_header "RETRIEVING INFRASTRUCTURE IDs"
    
    log_info "Getting API Gateway ID..."
    API_GATEWAY_ID=$(get_stack_output "$MAIN_STACK" "AWSOpsWheelAPI")
    
    log_info "Getting S3 bucket name..."
    S3_BUCKET=$(aws cloudformation list-stack-resources \
        --stack-name "$SOURCE_BUCKET_STACK" \
        --query 'StackResourceSummaries[?LogicalResourceId==`SourceS3Bucket`].PhysicalResourceId' \
        --output text \
        --region "$REGION")
    
    log_info "Getting static directory from S3..."
    STATIC_DIR=$(aws s3 ls "s3://$S3_BUCKET/" | grep "static_" | awk '{print $2}' | sed 's|/||' | tail -1)
    
    log_success "Infrastructure IDs retrieved:"
    log_info "  API Gateway: $API_GATEWAY_ID"
    log_info "  S3 Bucket: $S3_BUCKET"
    log_info "  Static Directory: $STATIC_DIR"
    
    # Export for use in other functions
    export API_GATEWAY_ID S3_BUCKET STATIC_DIR
}

# Function to deploy CloudFront
deploy_cloudfront() {
    log_header "DEPLOYING CLOUDFRONT"
    
    log_info "Updating CloudFormation template with current resource IDs..."
    
    # Create backup of original template
    cp cloudformation/s3-cloudfront-secure.yml cloudformation/s3-cloudfront-secure.yml.bak
    
    # Update template with current values
    sed -i.tmp \
        -e "s/awsopswheelsourcebucket-sources3bucket-f216qbzsu0fv/$S3_BUCKET/g" \
        -e "s/lhk9hgohl5.execute-api.us-west-2.amazonaws.com/$API_GATEWAY_ID.execute-api.$REGION.amazonaws.com/g" \
        -e "s/static_a3031aac-f60a-41e1-b60c-20dc8d48c4fa/$STATIC_DIR/g" \
        cloudformation/s3-cloudfront-secure.yml
    
    log_info "Deploying CloudFront stack..."
    if stack_exists "$CLOUDFRONT_STACK"; then
        log_info "CloudFront stack exists, updating..."
        aws cloudformation update-stack \
            --stack-name "$CLOUDFRONT_STACK" \
            --template-body file://cloudformation/s3-cloudfront-secure.yml \
            --region "$REGION" || {
                log_warning "No updates to perform on CloudFront stack"
            }
        
        if aws cloudformation describe-stacks --stack-name "$CLOUDFRONT_STACK" --region "$REGION" \
            --query 'Stacks[0].StackStatus' --output text | grep -q "UPDATE_IN_PROGRESS"; then
            wait_for_stack "$CLOUDFRONT_STACK" "update"
        fi
    else
        log_info "Creating new CloudFront stack..."
        aws cloudformation create-stack \
            --stack-name "$CLOUDFRONT_STACK" \
            --template-body file://cloudformation/s3-cloudfront-secure.yml \
            --region "$REGION"
        
        wait_for_stack "$CLOUDFRONT_STACK" "create"
    fi
    
    log_success "CloudFront deployed successfully"
    
    # Clean up temporary file
    rm -f cloudformation/s3-cloudfront-secure.yml.tmp
}

# Function to update frontend and deploy
update_frontend() {
    log_header "UPDATING FRONTEND"
    
    log_info "Getting CloudFront domain..."
    CLOUDFRONT_DOMAIN=$(get_stack_output "$CLOUDFRONT_STACK" "CloudFrontDomainName")
    
    log_info "Updating frontend configuration to point to CloudFront..."
    echo "module.exports = 'https://$CLOUDFRONT_DOMAIN';" > ui/development_app_location.js
    
    log_info "Building frontend..."
    ./run build_ui
    
    log_info "Syncing static files to S3..."
    NEW_STATIC_DIR=$(get_latest_static_dir)
    
    if [[ -z "$NEW_STATIC_DIR" ]]; then
        log_error "No static directory found in build/"
        exit 1
    fi
    
    log_info "Using static directory: $NEW_STATIC_DIR"
    aws s3 sync "build/$NEW_STATIC_DIR/" "s3://$S3_BUCKET/app/static/" --region "$REGION"
    
    log_success "Frontend updated and deployed"
    log_success "CloudFront Domain: https://$CLOUDFRONT_DOMAIN"
    
    # Clear CloudFront cache
    log_info "Clearing CloudFront cache..."
    DISTRIBUTION_ID=$(get_stack_output "$CLOUDFRONT_STACK" "CloudFrontDistributionId")
    
    if aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/*" \
        --region "$REGION" >/dev/null 2>&1; then
        log_success "CloudFront cache cleared - users will see fresh content immediately"
    else
        log_warning "CloudFront cache invalidation failed (IAM permission needed)"
        log_warning "Users may see cached content for up to 24 hours"
        log_info "To fix: Add 'cloudfront:CreateInvalidation' permission to your IAM user"
        log_info "Alternative: Wait 24 hours or clear cache manually in AWS Console"
    fi
}

# Function for update-only mode
update_app_only() {
    log_header "UPDATE APP ONLY MODE"
    
    # Get current infrastructure IDs
    get_infrastructure_ids
    
    # Update frontend (CloudFront is always required)
    update_frontend
}

# Function to delete all stacks
delete_stacks() {
    log_header "DELETING AWS OPS WHEEL STACKS"
    
    log_warning "This will delete ALL AWS Ops Wheel resources!"
    log_warning "Stacks to be deleted:"
    log_warning "  - $CLOUDFRONT_STACK"
    log_warning "  - $MAIN_STACK"  
    log_warning "  - $SOURCE_BUCKET_STACK"
    
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Deletion cancelled"
        exit 0
    fi
    
    # Step 1: Delete CloudFront stack first (if exists)
    if stack_exists "$CLOUDFRONT_STACK"; then
        log_info "Deleting CloudFront stack: $CLOUDFRONT_STACK"
        aws cloudformation delete-stack --stack-name "$CLOUDFRONT_STACK" --region "$REGION"
        wait_for_stack "$CLOUDFRONT_STACK" "delete"
        log_success "CloudFront stack deleted"
    else
        log_info "CloudFront stack $CLOUDFRONT_STACK does not exist, skipping"
    fi
    
    # Step 2: Empty S3 bucket before deleting source bucket stack
    if stack_exists "$SOURCE_BUCKET_STACK"; then
        log_info "Getting S3 bucket name for cleanup..."
        S3_BUCKET=$(aws cloudformation list-stack-resources \
            --stack-name "$SOURCE_BUCKET_STACK" \
            --query 'StackResourceSummaries[?LogicalResourceId==`SourceS3Bucket`].PhysicalResourceId' \
            --output text \
            --region "$REGION" 2>/dev/null || echo "")
        
        if [[ -n "$S3_BUCKET" ]]; then
            log_info "Attempting to empty S3 bucket: $S3_BUCKET"
            
            # Basic cleanup attempt
            aws s3 rm "s3://$S3_BUCKET" --recursive --region "$REGION" 2>/dev/null || {
                log_warning "Could not empty S3 bucket automatically"
            }
            
            # Suspend versioning
            aws s3api put-bucket-versioning \
                --bucket "$S3_BUCKET" \
                --versioning-configuration Status=Suspended \
                --region "$REGION" 2>/dev/null || {
                log_warning "Could not suspend bucket versioning"
            }
            
            log_warning "If stack deletion fails due to S3 bucket not empty:"
            log_warning "  1. Go to AWS Console → S3"
            log_warning "  2. Find bucket: $S3_BUCKET"
            log_warning "  3. Enable 'Show versions' toggle"
            log_warning "  4. Select all objects and versions, then delete"
            log_warning "  5. Delete the bucket manually"
            log_warning "  6. Re-run this script"
        else
            log_warning "Could not determine S3 bucket name, proceeding with stack deletion"
        fi
    fi
    
    # Step 3: Delete main application stack
    if stack_exists "$MAIN_STACK"; then
        log_info "Deleting main application stack: $MAIN_STACK"
        aws cloudformation delete-stack --stack-name "$MAIN_STACK" --region "$REGION"
        wait_for_stack "$MAIN_STACK" "delete"
        log_success "Main application stack deleted"
    else
        log_info "Main stack $MAIN_STACK does not exist, skipping"
    fi
    
    # Step 4: Delete source bucket stack
    if stack_exists "$SOURCE_BUCKET_STACK"; then
        log_info "Deleting source bucket stack: $SOURCE_BUCKET_STACK"
        aws cloudformation delete-stack --stack-name "$SOURCE_BUCKET_STACK" --region "$REGION"
        wait_for_stack "$SOURCE_BUCKET_STACK" "delete"
        log_success "Source bucket stack deleted"
    else
        log_info "Source bucket stack $SOURCE_BUCKET_STACK does not exist, skipping"
    fi
    
    log_header "ALL STACKS DELETED SUCCESSFULLY"
    log_success "AWS Ops Wheel has been completely removed from your AWS account"
}

# Main execution
main() {
    log_header "AWS OPS WHEEL STREAMLINED DEPLOYMENT"
    log_info "Starting deployment process..."
    log_info "Region: $REGION"
    log_info "Main Stack: $MAIN_STACK"
    log_info "CloudFront Stack: $CLOUDFRONT_STACK"
    
    if [[ "$DELETE_STACKS" == "true" ]]; then
        delete_stacks
        return
    fi
    
    if [[ "$UPDATE_ONLY" == "true" ]]; then
        update_app_only
    else
        # Full deployment (CloudFront is always required)
        deploy_main_app
        get_infrastructure_ids
        deploy_cloudfront
        update_frontend
    fi
    
    # Cleanup old static directories
    if [[ "$CLEANUP_LOCAL" == "true" ]]; then
        cleanup_old_static_dirs "$KEEP_COUNT" "local"
    fi
    
    if [[ "$CLEANUP_S3" == "true" ]]; then
        if [[ -n "$S3_BUCKET" ]]; then
            cleanup_old_static_dirs "$KEEP_COUNT" "s3"
        else
            log_warning "S3 bucket not found, skipping S3 cleanup"
        fi
    fi
    
    log_header "DEPLOYMENT COMPLETED SUCCESSFULLY"
}

# Run main function
main
