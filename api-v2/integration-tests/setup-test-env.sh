#!/bin/bash

# AWS Ops Wheel v2 Integration Test Environment Setup
# This script extracts configuration from your deployed CloudFormation stack
# and creates a .env file for integration tests

set -e

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

# Function to show usage
show_usage() {
    echo "AWS Ops Wheel v2 Test Environment Setup"
    echo ""
    echo "Usage: $0 [OPTIONS] <suffix>"
    echo ""
    echo "Arguments:"
    echo "  suffix               Deployment suffix (e.g., dev, staging, myname)"
    echo ""
    echo "Options:"
    echo "  -r, --region REGION  AWS region (default: us-west-2)"
    echo "  -f, --force         Overwrite existing .env file"
    echo "  -o, --output FILE   Output file (default: .env)"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 dev                          # Extract from aws-ops-wheel-v2-dev"
    echo "  $0 myname --region us-east-1    # Extract from aws-ops-wheel-v2-myname in us-east-1"
    echo "  $0 staging --output .env.staging # Output to custom file"
    echo ""
    echo "This script will:"
    echo "  1. Check that AWS CLI is configured"
    echo "  2. Verify the CloudFormation stack exists"
    echo "  3. Extract stack outputs (API URL, Frontend URL, Cognito IDs)"
    echo "  4. Create .env file with extracted configuration"
    echo "  5. Validate the configuration"
}

# Parse command line arguments
SUFFIX=""
REGION="us-west-2"
FORCE=false
OUTPUT_FILE=".env"

while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [ -z "$SUFFIX" ]; then
                SUFFIX="$1"
                shift
            else
                log_error "Multiple suffixes provided: $SUFFIX and $1"
                show_usage
                exit 1
            fi
            ;;
    esac
done

# Validate required arguments
if [ -z "$SUFFIX" ]; then
    log_error "Suffix is required"
    show_usage
    exit 1
fi

# Set stack name
STACK_NAME="aws-ops-wheel-v2-${SUFFIX}"

log_info "Setting up test environment for AWS Ops Wheel v2"
log_info "Stack Name: $STACK_NAME"
log_info "Region: $REGION"
log_info "Output File: $OUTPUT_FILE"
echo

# Check if AWS CLI is configured
check_aws_config() {
    log_info "Checking AWS CLI configuration..."
    
    if ! command -v aws >/dev/null 2>&1; then
        log_error "AWS CLI is not installed. Please install AWS CLI first."
        exit 1
    fi
    
    if ! aws sts get-caller-identity > /dev/null 2>&1; then
        log_error "AWS CLI is not configured properly. Please run 'aws configure'"
        exit 1
    fi
    
    local account_id=$(aws sts get-caller-identity --query Account --output text)
    local current_region=$(aws configure get region || echo "not-set")
    
    log_success "AWS CLI configured for account: $account_id"
    
    if [ "$current_region" != "$REGION" ]; then
        log_warning "Current AWS CLI region ($current_region) differs from specified region ($REGION)"
        log_info "Using specified region: $REGION"
    fi
}

# Check if output file exists and handle overwrite
check_output_file() {
    if [ -f "$OUTPUT_FILE" ] && [ "$FORCE" != true ]; then
        log_warning "Output file already exists: $OUTPUT_FILE"
        echo -n "Overwrite? [y/N]: "
        read -r response
        if [[ ! $response =~ ^[Yy]$ ]]; then
            log_info "Aborted by user"
            exit 0
        fi
    fi
}

# Verify stack exists and get outputs
extract_stack_outputs() {
    log_info "Checking CloudFormation stack: $STACK_NAME"
    
    # Check if stack exists
    local stack_info
    stack_info=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" 2>/dev/null || echo "")
    
    if [ -z "$stack_info" ]; then
        log_error "Stack not found: $STACK_NAME in region $REGION"
        log_error "Make sure you've deployed the stack first:"
        log_error "  ./deploy-v2.sh --suffix $SUFFIX --region $REGION"
        exit 1
    fi
    
    # Check stack status
    local stack_status
    stack_status=$(echo "$stack_info" | jq -r '.Stacks[0].StackStatus' 2>/dev/null || echo "UNKNOWN")
    
    case "$stack_status" in
        "CREATE_COMPLETE"|"UPDATE_COMPLETE")
            log_success "Stack found and ready: $stack_status"
            ;;
        "CREATE_IN_PROGRESS"|"UPDATE_IN_PROGRESS")
            log_error "Stack is currently updating: $stack_status"
            log_error "Please wait for the stack update to complete"
            exit 1
            ;;
        *)
            log_warning "Stack status: $stack_status"
            log_warning "This may cause configuration extraction to fail"
            ;;
    esac
    
    # Extract outputs
    log_info "Extracting stack outputs..."
    
    local outputs
    outputs=$(echo "$stack_info" | jq -r '.Stacks[0].Outputs[]? | "\(.OutputKey)=\(.OutputValue)"' 2>/dev/null)
    
    if [ -z "$outputs" ]; then
        log_error "No outputs found in stack. This may indicate a deployment issue."
        exit 1
    fi
    
    # Parse outputs into variables using portable approach
    # Extract each value directly using grep to avoid associative arrays
    API_BASE_URL=$(echo "$outputs" | grep "^ApiGatewayURL=" | cut -d'=' -f2-)
    FRONTEND_URL=$(echo "$outputs" | grep "^FrontendURL=" | cut -d'=' -f2-)
    USER_POOL_ID=$(echo "$outputs" | grep "^UserPoolId=" | cut -d'=' -f2-)
    CLIENT_ID=$(echo "$outputs" | grep "^UserPoolClientId=" | cut -d'=' -f2-)
    
    # Validate required outputs exist
    local missing_outputs=()
    
    if [ -z "$API_BASE_URL" ]; then
        missing_outputs+=("ApiGatewayURL")
    fi
    if [ -z "$FRONTEND_URL" ]; then
        missing_outputs+=("FrontendURL")
    fi
    if [ -z "$USER_POOL_ID" ]; then
        missing_outputs+=("UserPoolId")
    fi
    if [ -z "$CLIENT_ID" ]; then
        missing_outputs+=("UserPoolClientId")
    fi
    
    if [ ${#missing_outputs[@]} -gt 0 ]; then
        log_error "Missing required stack outputs: ${missing_outputs[*]}"
        log_error "This indicates an incomplete or failed deployment"
        exit 1
    fi
    
    # Append API path to base URL if not already present
    if [[ "$API_BASE_URL" != */app/api/v2 ]]; then
        API_BASE_URL="${API_BASE_URL}/app/api/v2"
    fi
    
    log_success "Configuration extracted successfully:"
    log_info "  API URL: $API_BASE_URL"
    log_info "  Frontend URL: $FRONTEND_URL"
    log_info "  User Pool ID: $USER_POOL_ID"
    log_info "  Client ID: $CLIENT_ID"
}

# Create .env file
create_env_file() {
    log_info "Creating environment file: $OUTPUT_FILE"
    
    cat > "$OUTPUT_FILE" << EOF
# AWS Ops Wheel v2 Integration Test Configuration
# Generated automatically from CloudFormation stack: $STACK_NAME
# Generated at: $(date)
# Region: $REGION

# =============================================================================
# REQUIRED CONFIGURATION (Extracted from CloudFormation)
# =============================================================================

AWS_OPS_WHEEL_API_BASE_URL=$API_BASE_URL
AWS_OPS_WHEEL_FRONTEND_URL=$FRONTEND_URL
AWS_OPS_WHEEL_USER_POOL_ID=$USER_POOL_ID
AWS_OPS_WHEEL_CLIENT_ID=$CLIENT_ID

# =============================================================================
# OPTIONAL CONFIGURATION (Defaults)
# =============================================================================

AWS_OPS_WHEEL_AWS_REGION=$REGION
AWS_OPS_WHEEL_CLEANUP_ENABLED=true
AWS_OPS_WHEEL_TIMEOUT_SECONDS=15
AWS_OPS_WHEEL_MAX_RETRIES=3
AWS_OPS_WHEEL_RETRY_DELAY=1.0
AWS_OPS_WHEEL_REQUEST_TIMEOUT=15
AWS_OPS_WHEEL_USE_DYNAMIC_ADMIN=true

# Test execution settings (adjust as needed)
AWS_OPS_WHEEL_PARALLEL_SAFE=false
AWS_OPS_WHEEL_AGGRESSIVE_TESTING=false
AWS_OPS_WHEEL_ENVIRONMENT_SUFFIX=$SUFFIX

# =============================================================================
# USAGE
# =============================================================================

# Run all tests:
#   python -m pytest
#
# Run specific test file:
#   python -m pytest tests/test_deployment_admin_workflows.py
#
# Run with verbose output:
#   python -m pytest -v
#
# To regenerate this file:
#   ./setup-test-env.sh $SUFFIX --region $REGION

EOF

    log_success "Environment file created: $OUTPUT_FILE"
}

# Install dependencies if needed
install_dependencies() {
    log_info "Checking Python dependencies..."
    
    # Check if python-dotenv is available
    if ! python3 -c "import dotenv" >/dev/null 2>&1; then
        log_info "Installing required dependencies..."
        
        if [ -f "requirements.txt" ]; then
            pip3 install -r requirements.txt
            if [ $? -eq 0 ]; then
                log_success "Dependencies installed successfully"
            else
                log_error "Failed to install dependencies"
                exit 1
            fi
        else
            log_warning "requirements.txt not found, installing python-dotenv directly"
            pip3 install python-dotenv>=1.0.0
        fi
    else
        log_success "Dependencies already installed"
    fi
}

# Fix test file paths to prevent duplication
fix_test_paths() {
    log_info "Ensuring test files have correct API paths..."
    
    # List of files that may contain /app/api/v2/ paths that need fixing
    local test_files=(
        "conftest.py"
        "config/test_config.py"
        "tests/test_00_deployment_admin_workflows.py"
        "tests/test_01_admin_workflows.py"
        "tests/test_02_wheel_admin_workflows.py"
        "tests/test_03_user_workflows.py"
        "tests/test_04_cross_role_scenarios.py"
        "utils/auth_manager.py"
    )
    
    local files_fixed=0
    
    for file in "${test_files[@]}"; do
        if [ -f "$file" ]; then
            # Check if file contains the problematic path
            if grep -q "/app/api/v2/" "$file" 2>/dev/null; then
                # Create backup
                cp "$file" "${file}.backup"
                
                # Fix the paths - remove /app/api/v2/ prefix since base URL already includes it
                sed -i.tmp 's|/app/api/v2/|/|g' "$file" && rm -f "${file}.tmp"
                
                if [ $? -eq 0 ]; then
                    files_fixed=$((files_fixed + 1))
                    log_info "  ✓ Fixed paths in $file"
                else
                    log_warning "  ⚠ Could not fix paths in $file, restoring backup"
                    mv "${file}.backup" "$file"
                fi
            fi
        fi
    done
    
    if [ $files_fixed -gt 0 ]; then
        log_success "Fixed API paths in $files_fixed test files"
        log_info "  This prevents URL duplication issues with the new test environment"
    else
        log_success "Test files already have correct API paths"
    fi
}

# Validate configuration
validate_config() {
    log_info "Validating configuration..."
    
    # Source the environment file to test it
    if ! source "$OUTPUT_FILE" 2>/dev/null; then
        log_error "Failed to source $OUTPUT_FILE - invalid format"
        exit 1
    fi
    
    # Test configuration with Python
    # Export environment variables to subprocess
    export AWS_OPS_WHEEL_API_BASE_URL="$API_BASE_URL"
    export AWS_OPS_WHEEL_FRONTEND_URL="$FRONTEND_URL" 
    export AWS_OPS_WHEEL_USER_POOL_ID="$USER_POOL_ID"
    export AWS_OPS_WHEEL_CLIENT_ID="$CLIENT_ID"
    export AWS_OPS_WHEEL_AWS_REGION="$REGION"
    export AWS_OPS_WHEEL_ENVIRONMENT_SUFFIX="$SUFFIX"
    
    python3 << EOF
import sys
import os

# Add the config path to import test_config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'config'))

try:
    from test_config import TestConfig
    
    # Create config instance using environment variables (no specific environment)
    config = TestConfig()
    
    # Validate configuration
    config.validate_config()
    
    print("✅ Configuration validation successful")
    print(f"✅ Using {config.get_configuration_source()}")
    print(f"✅ API URL: {config.api_base_url}")
    print(f"✅ Frontend URL: {config.frontend_url}")
    
except Exception as e:
    print(f"❌ Configuration validation failed: {e}")
    sys.exit(1)
EOF

    if [ $? -eq 0 ]; then
        log_success "Configuration validation passed"
    else
        log_error "Configuration validation failed"
        exit 1
    fi
}

# Test API connectivity
test_api_connectivity() {
    log_info "Testing API connectivity..."
    
    # Simple health check to verify the API is reachable
    local health_url="${API_BASE_URL%/app/api/v2}/health"
    local response_code
    
    response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$health_url" 2>/dev/null || echo "000")
    
    case "$response_code" in
        "200"|"404"|"403")
            log_success "API endpoint is reachable (HTTP $response_code)"
            ;;
        "000")
            log_warning "Could not connect to API endpoint - this may be normal if there's no health endpoint"
            log_info "  API URL: $health_url"
            ;;
        *)
            log_warning "API endpoint returned unexpected status: $response_code"
            log_info "  This may indicate a configuration issue"
            ;;
    esac
}

# Main execution
main() {
    echo "🚀 AWS Ops Wheel v2 Test Environment Setup"
    echo
    
    check_aws_config
    check_output_file
    extract_stack_outputs
    create_env_file
    install_dependencies
    fix_test_paths
    validate_config
    test_api_connectivity
    
    echo
    log_success "🎉 Test environment setup completed successfully!"
    echo
    log_info "Next steps:"
    log_info "  1. Review the configuration in $OUTPUT_FILE"
    log_info "  2. Run integration tests: python -m pytest --verbose"
    log_info "  3. Run specific tests: python -m pytest tests/test_01_admin_workflows.py -v"
    log_info "  4. Run with coverage: python -m pytest --verbose --cov-report term-missing --cov ./"
    echo
    log_info "Example test commands:"
    log_info "  # All tests with verbose output"
    log_info "  python -m pytest --verbose"
    echo
    log_info "  # Single test file"
    log_info "  python -m pytest tests/test_03_user_workflows.py -v"
    echo
    log_info "  # With HTML reports"
    log_info "  python -m pytest --verbose --html=reports/report.html --self-contained-html"
    echo
    log_info "To see detailed configuration info:"
    log_info "  python -c \"from config.test_config import TestConfig; TestConfig().print_configuration_info()\""
}

# Execute main function
main
