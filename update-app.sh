#!/bin/bash

# Quick App Update Script
# This script provides a simple way to update just the app without touching infrastructure

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
CLEANUP_LOCAL=true
CLEANUP_S3=false
KEEP_COUNT=2

# Function to show usage
show_usage() {
    cat << EOF
Quick App Update Script

Usage: $0 [OPTIONS]

OPTIONS:
    --cleanup-s3           Clean up old S3 static directories (keeps last 2)
    --no-cleanup-local     Skip cleanup of local static directories  
    --keep-count N         Number of static directories to keep (default: 2)
    -h, --help            Show this help message

EXAMPLES:
    # Quick update (default)
    $0

    # Update with S3 cleanup
    $0 --cleanup-s3

    # Update keeping more old directories
    $0 --keep-count 5
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
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
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}[ERROR]${NC} Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Function to get most recent static directory
get_latest_static_dir() {
    ls -t build/ | grep "static_" | head -1
}

# Function to cleanup old static directories (keep last N)
cleanup_old_static_dirs() {
    local keep_count=${1:-2}  # Keep last N directories (default: 2)
    local location=${2:-"local"}  # "local" or "s3"
    
    if [[ "$location" == "local" ]]; then
        echo -e "${BLUE}[INFO]${NC} Cleaning up old local static directories (keeping last $keep_count)..."
        local old_dirs=($(ls -t build/ | grep "static_" | tail -n +$((keep_count + 1))))
        
        for dir in "${old_dirs[@]}"; do
            if [[ -n "$dir" ]]; then
                echo -e "${BLUE}[INFO]${NC} Removing old local directory: build/$dir"
                rm -rf "build/$dir"
            fi
        done
    elif [[ "$location" == "s3" ]]; then
        echo -e "${BLUE}[INFO]${NC} Cleaning up old S3 static directories (keeping last $keep_count)..."
        local s3_dirs=($(aws s3 ls "s3://$S3_BUCKET/" | grep "static_" | awk '{print $2}' | sed 's|/||' | sort -r | tail -n +$((keep_count + 1))))
        
        for dir in "${s3_dirs[@]}"; do
            if [[ -n "$dir" ]]; then
                echo -e "${BLUE}[INFO]${NC} Removing old S3 directory: s3://$S3_BUCKET/$dir/"
                aws s3 rm "s3://$S3_BUCKET/$dir/" --recursive --region us-west-2
            fi
        done
    fi
}

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE} AWS OPS WHEEL - QUICK APP UPDATE${NC}"
echo -e "${BLUE}================================================================${NC}"

echo -e "${BLUE}[INFO]${NC} Building and updating app..."
./run build_ui

echo -e "${BLUE}[INFO]${NC} Finding most recent static directory..."
NEW_STATIC_DIR=$(ls -t build/ | grep static_ | head -1)

if [[ -z "$NEW_STATIC_DIR" ]]; then
    echo -e "${RED}[ERROR]${NC} No static directory found!"
    exit 1
fi

echo -e "${BLUE}[INFO]${NC} Using static directory: $NEW_STATIC_DIR"

# Get S3 bucket from CloudFormation
echo -e "${BLUE}[INFO]${NC} Getting S3 bucket name..."
S3_BUCKET=$(aws cloudformation list-stack-resources \
    --stack-name AWSOpsWheelSourceBucket \
    --query 'StackResourceSummaries[?LogicalResourceId==`SourceS3Bucket`].PhysicalResourceId' \
    --output text \
    --region us-west-2)

if [[ -z "$S3_BUCKET" ]]; then
    echo -e "${RED}[ERROR]${NC} Could not find S3 bucket. Make sure AWSOpsWheelSourceBucket stack exists."
    exit 1
fi

echo -e "${BLUE}[INFO]${NC} Syncing to S3 bucket: $S3_BUCKET"
aws s3 sync "build/$NEW_STATIC_DIR/" "s3://$S3_BUCKET/app/static/" --region us-west-2

echo -e "${GREEN}[SUCCESS]${NC} App updated successfully!"

# Optional: Clear CloudFront cache if CloudFront stack exists
if aws cloudformation describe-stacks --stack-name AWSOpsWheel-CloudFront --region us-west-2 >/dev/null 2>&1; then
    echo -e "${BLUE}[INFO]${NC} Clearing CloudFront cache..."
    DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
        --stack-name AWSOpsWheel-CloudFront \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
        --output text \
        --region us-west-2)
    
    if aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/*" \
        --region us-west-2 >/dev/null 2>&1; then
        echo -e "${GREEN}[SUCCESS]${NC} CloudFront cache cleared - users will see fresh content immediately!"
    else
        echo -e "${YELLOW}[WARNING]${NC} CloudFront cache invalidation failed (IAM permission needed)"
        echo -e "${YELLOW}[WARNING]${NC} Users may see cached content for up to 24 hours"
        echo -e "${BLUE}[INFO]${NC} To fix: Add 'cloudfront:CreateInvalidation' permission to your IAM user"
    fi
fi

# Cleanup old static directories
if [[ "$CLEANUP_LOCAL" == "true" ]]; then
    cleanup_old_static_dirs "$KEEP_COUNT" "local"
fi

if [[ "$CLEANUP_S3" == "true" ]]; then
    if [[ -n "$S3_BUCKET" ]]; then
        cleanup_old_static_dirs "$KEEP_COUNT" "s3"
    else
        echo -e "${YELLOW}[WARNING]${NC} S3 bucket not found, skipping S3 cleanup"
    fi
fi

echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN} UPDATE COMPLETED!${NC}"
echo -e "${GREEN}================================================================${NC}"
