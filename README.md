# AWS Ops Wheel - Enhanced Multi-Tenant Edition

The AWS Ops Wheel is a tool that simulates a random selection from a group of participants that weights away from participants recently chosen. For any group, the selection can also be rigged to suggest a particular participant that will be selected in a blatantly obvious (and sometimes hilarious) way. **Version 2.0** introduces multi-tenant architecture, advanced user management, and enterprise-grade security features.

## Quick Start (Recommended V2)

Deploy the enhanced multi-tenant version with advanced features:

**Option 1: V2 Deployment (Recommended)**
```bash
./deploy-v2.sh --suffix dev --admin-email your@email.com
```

**Option 2: Legacy V1 Deployment**
```bash
./deploy.sh --email your@email.com --suffix dev
```
## Version Comparison

| Feature | V1 (Legacy) | V2 (Enhanced) |
|---------|-------------|---------------|
| Architecture | Single-tenant | **Multi-tenant with Wheel Groups** |
| User Management | Basic Cognito | **Advanced roles & permissions** |
| Security | Standard | **Fine-grained access control** |
| Data Isolation | None | **Complete organizational separation** |
| Role System | Admin/User | **ADMIN, WHEEL_ADMIN, USER, DEPLOYMENT_ADMIN** |

## How It Works

### Core Concept
The AWS Ops Wheel provides **fair random selection** with intelligent weighting that reduces the probability of selecting recently chosen participants. This ensures balanced distribution over time while maintaining the element of surprise.

### Selection Algorithm
The enhanced weighting system works as follows:

```python
def suggest_participant(wheel):
    target_number = len(wheel) * random()  # Random number between 0 and total_weight
    participant = None
    for participant in wheel:
        target_number -= participant.weight
        if target_number <= 0:
            break
    return participant

def select_participant(chosen, wheel):
    # Redistribute weight from chosen participant to others
    if len(wheel) > 1:
        weight_slice = chosen.weight / (len(wheel) - 1)
        for participant in wheel:
            if participant == chosen:
                participant.weight = 0  # Chosen participant gets zero weight
            else:
                participant.weight += weight_slice  # Others get increased weight
```

This algorithm ensures recently chosen participants have lower probability of being selected again, promoting fairness over time.

# Operations Guide

## V2 Enhanced Operations

### Wheel Group Operations
***Notes:*** Wheel Groups are isolated organizational containers in V2's multi-tenant architecture

- **Create a wheel group**: Set up a new organization with custom settings, quotas, and branding
  - Requires wheel group name and admin user email
  - Automatically creates the first admin user for the group
  - Configurable resource limits (max wheels, max participants per wheel)
  - Custom themes and organizational settings
- **Update wheel group settings**: Modify quotas, themes, and organizational preferences
- **View wheel group statistics**: See user count, wheel count, activity metrics, and usage analytics
- **Delete wheel group**: Permanently remove the entire organization and ALL associated data
  - ***Warning:*** This is irreversible and deletes all wheels, participants, and users

### Enhanced Wheel Operations
***Notes:*** Wheels are scoped to their wheel group with advanced multi-tenant features

- **Create a new wheel**: Set up participant selection groups within your wheel group
  - Supports custom names, descriptions, and selection limits
  - Configurable participant weight defaults
  - Optional wheel templates for consistency
- **Edit an existing wheel**: Modify settings, appearance, and selection parameters
- **Delete a wheel**: Remove wheel and all associated participants
- **Multi-Select Spin**: Select multiple participants simultaneously (up to 30)
  - ***Notes:*** Weights are adjusted proportionally for all selected participants
- **Single Spin**: Traditional single participant selection with enhanced animations
  - ***Notes:*** This does not adjust weighting, so if you're unhappy with the result, you can spin again
- **Proceed**: Accept the suggested participant(s) and adjust weights accordingly
- **Reset**: Restart all participants to equal weights as 1.0
- **Export wheel data**: Download participant lists and selection history
- **Duplicate wheel**: Create copies with same participants but fresh weights

### Advanced Participant Operations
***Notes:*** Participants have enhanced profiles and are isolated within wheel groups

- **Add participants to a wheel**: Create new participants with rich metadata
  - Requires name and follow-through URL that opens in a new browser tab when selected
  - Participants begin with configurable default weight (typically 1.0)
  - Optional email, tags, and custom attributes
  - Batch import support via CSV upload
- **Edit participant details**: Update name, URL, weight, tags, and metadata
- **Delete specific participants**: Remove individuals from wheels
- **Bulk participant management**: Mass updates, imports, and exports
- **Advanced rigging**: Configure participants to be selected next
  - Doesn't change actual weighting - bypasses selection algorithm temporarily
  - After proceeding, weights adjust as if participant was selected normally
  - Can be hidden (deceptive) or visible (comical demonstration mode)
  - Supports multi-participant rigging for complex scenarios
- **Participant history**: View selection history, frequency, and weight changes over time
- **Weight management**: Fine-tune individual participant probabilities

### User Management Operations (V2 Multi-Tenant)
***Notes:*** Users belong to wheel groups with role-based permissions

- **Create users**: Add team members to your wheel group with appropriate roles
  - Supports ADMIN, WHEEL_ADMIN, and USER roles
  - Automatic Cognito user creation with temporary passwords
  - Email verification and welcome workflows
- **Update user roles**: Change permissions within the wheel group
- **Delete users**: Remove users from both the wheel group and authentication system
- **Invite users**: Send invitations to join the wheel group
- **User activity monitoring**: Track login history and wheel usage
- **Bulk user import**: CSV-based user creation for large teams

### Deployment Admin Operations (Platform Management)
***Notes:*** Deployment Admins have cross-group platform oversight

- **List all wheel groups**: View every organization with statistics and activity metrics
  - See user counts, wheel counts, creation dates, and last activity
  - System-wide usage analytics and health monitoring
- **Delete wheel groups**: Permanently remove entire organizations (emergency use)
  - Deletes ALL associated wheels, participants, users, and data
  - Removes users from both DynamoDB and Cognito
  - Complete cleanup with no recovery option
  - ***Warning:*** This is the most destructive operation in the system
- **System monitoring**: Platform-wide health checks and performance metrics
- **Cross-tenant troubleshooting**: Debug issues across organizations
- **Platform maintenance**: System updates, cleanup, and optimization

## V1 Legacy Operations

### Basic Wheel Operations (V1)
***Notes:*** V1 provides single-tenant wheel management

- **Create a new wheel**: Set up basic participant selection groups
- **Edit an existing wheel**: Modify wheel settings and appearance  
- **Delete a wheel**: Remove wheel and associated participants
- **Spin the wheel**: Traditional single participant selection
  - ***Notes:*** This does not adjust weighting, so if you're unhappy with the result, you can spin again
- **Proceed**: Accept the suggested participant and adjust weights
- **Reset**: Restart all participants to equal weights as 1.0

### Basic Participant Operations (V1)
***Notes:*** Participants aren't shared between wheels in V1

- **Add a participant to a wheel**: Create new participants with basic information
  - Requires name and URL that opens in a new browser tab when selected
  - Participants begin with weight of 1.0 (average weight for all participants)
- **Edit participant's name and/or URL**: Update basic participant information
- **Delete specific participants**: Remove individuals from the wheel
- **Rig a specific participant**: Configure participant to be selected next
  - Doesn't change weighting - bypasses suggestion algorithm until proceeding
  - After proceeding, weights adjust as if participant was selected normally
  - Can be hidden (deceptive) or non-hidden (comical demonstration)

### Authentication and User Management (V1)
***Notes:*** V1 uses basic Cognito authentication without multi-tenant features

- **Admin user management**: Simple user creation through Cognito console
- **Password management**: Basic password reset and recovery
- **Single organization**: All users share the same wheel instance

## Screenshots
### Wheels Table (V2 Enhanced)
![Wheels Table](screenshots/wheels_table.png)
*Multi-tenant wheel management with group isolation*

### Participants Table (V2 Enhanced)
![Participants Table](screenshots/participants_table.png)
*Advanced participant management with role-based access*

### Wheel Interface (Pre-spin)
![Wheel Pre-spin](screenshots/wheel_pre_spin.png)
*Enhanced UI with improved user experience*

### Wheel Interface (Post-spin)
![Wheel Post-spin](screenshots/wheel_post_spin.png)
*Real-time selection with smooth animations*

# User Guide

## V2 Core Concepts

### Wheel Groups
**Wheel Groups** are isolated organizational containers that provide:
- **Data Isolation**: Complete separation between organizations
- **User Management**: Role-based access control within groups
- **Resource Quotas**: Configurable limits for wheels and participants
- **Custom Settings**: Organization-specific configurations
- **Multi-Tenant Security**: Zero data leakage between groups

### User Roles & Permissions
- **ADMIN**: Full wheel group management and user administration
- **WHEEL_ADMIN**: Wheel and participant management within the group
- **USER**: Basic wheel operation and viewing permissions
- **DEPLOYMENT_ADMIN**: Cross-group administrative access for platform management

### Enhanced Wheel Operations
- **Create/Edit/Delete** wheels within your wheel group
- **Multi-Select Spin**: Select multiple participants simultaneously (up to 30)
- **Advanced Rigging**: Hide or display rigged selections for demonstrations
- **Wheel Templates**: Reusable wheel configurations
- **Audit Trail**: Complete history of all wheel operations
- **Bulk Operations**: Mass updates and configurations

### Participant Management
- **Batch Import**: CSV upload for bulk participant creation
- **Custom Weights**: Fine-tune selection probabilities
- **Follow-through URLs**: Direct links when participants are selected
- **Participant Profiles**: Enhanced metadata and history tracking
- **Group-Scoped Participants**: Complete isolation per wheel group

## Legacy V1 Concepts
V1 provides the original single-tenant experience:
- **Single Wheel Instance**: One wheel per deployment
- **Basic Authentication**: Simple Cognito user management  
- **Standard Operations**: Create, spin, proceed, reset functionality
- **Simple Participant Management**: Add/edit/delete with basic weighting

# 🛠️ Development Guide

## Development Dependencies

### V2 Requirements (Recommended)
- **Node.js** 16.x+ (for enhanced UI features)
- **Python** 3.9+ (for Lambda compatibility)
- **AWS CLI** 2.x+ with proper permissions
- **Dependencies**:
  ```bash
  # Python packages
  pip install -r requirements.txt
  
  # Node.js packages (for UI development)  
  cd ui-v2 && npm install
  ```

### V1 Requirements (Legacy Support)
- **Node.js** 6.10+
- **Python** 3.x
- **AWS CLI** 1.11+

## AWS Permissions & Setup

### Recommended: Dedicated IAM User
Create a dedicated IAM user for development:

1. **Create Custom Policy**: Use the policy in [`cloudformation/awsopswheel-create-policy.json`](cloudformation/awsopswheel-create-policy.json)
2. **Create IAM User**: Attach the policy and enable programmatic access
3. **Configure AWS CLI**:
   ```bash
   aws configure
   # Enter your access key, secret key, and preferred region
   ```

### Required AWS Services
- **CloudFormation**: Stack management and nested templates
- **Lambda**: Serverless compute with layer optimization
- **API Gateway**: REST API hosting with enhanced security
- **DynamoDB**: Multi-tenant data storage with isolation
- **Cognito**: Advanced authentication with custom attributes
- **S3**: Static hosting and build artifacts
- **CloudFront**: Global CDN distribution (V2 enhanced deployment)

## Testing

### V2 Comprehensive Testing
```bash
# Unit Tests
cd api-v2 && python -m pytest tests/ -v

# Integration Tests  

# Update Deployment
./deploy-v2.sh --suffix test
cd api-v2/integration-tests 
# Setup Test Env
./setup-test-env.sh test
python -m pytest --verbose

# Cross-tenant isolation tests
cd api-v2/integration-tests && python -m pytest tests/test_04_cross_role_scenarios.py
```

### V1 Legacy Testing
```bash
# API Tests
cd api && pytest --verbose --cov-report term-missing --cov ./ -s

# UI Tests
cd ui && npm run test
```

# 🚀 Deployment Guide

## V2 Enhanced Deployment (Recommended)

### Quick Deployment
```bash
# Full deployment with CloudFront
./deploy-v2.sh --suffix dev --admin-email your@email.com

# Multiple environments
./deploy-v2.sh --suffix staging --admin-email admin@company.com
./deploy-v2.sh --suffix prod --admin-email prod-admin@company.com
```

### Advanced Options
```bash
# Custom configuration
./deploy-v2.sh \
  --suffix myteam \
  --region us-east-1 \
  --admin-email admin@myteam.com \
  --admin-username teamadmin

# Quick app updates (no infrastructure changes)
./deploy-v2.sh --quick-update --suffix dev

# Clean removal
./deploy-v2.sh --delete --suffix dev
```

### V2 Deployment Features
- **Modular CloudFormation**: Nested stacks for better organization
- **Content-Hash Layers**: Efficient Lambda layer caching and versioning
- **Security Validation**: Pre-deployment security checks
- **CloudFront Integration**: Global CDN deployment with cache invalidation
- **Multi-Environment**: Support for dev/staging/prod workflows
- **Automated Cleanup**: Old resources and layer management

## V1 Legacy Deployment

### Option 1: CloudFormation Launch
Use the launch button above or deploy directly:
```bash
aws cloudformation create-stack \
  --stack-name AWSOpsWheel \
  --template-url https://s3-us-west-2.amazonaws.com/aws-ops-wheel/cloudformation-template.yml \
  --parameters ParameterKey=AdminEmail,ParameterValue=your@email.com \
  --capabilities CAPABILITY_IAM
```

### Option 2: Manual Build & Deploy
```bash
# Traditional deployment
./deploy.sh --email your@email.com

# With custom suffix
./deploy.sh --email your@email.com --suffix dev
```

## Post-Deployment Setup

### V2 Multi-Tenant Setup
1. **Access Application**: Use the provided CloudFront URL
2. **Login as Deployment Admin**: Use provided temporary credentials
3. **Create Wheel Group**: Set up your organization with custom settings
4. **Invite Users**: Add team members with appropriate roles
5. **Configure Quotas**: Set limits and permissions per group
6. **Create Wheels**: Set up your selection wheels with templates
7. **Import Participants**: Use CSV import for bulk data

### V1 Single-Tenant Setup  
1. **Access Application**: Use the provided endpoint
2. **Login**: Use Cognito credentials from email
3. **Create Wheels**: Set up participant groups
4. **Start Spinning**: Begin fair selection process

# 🔧 Administration & Maintenance

## V2 Administrative Features

### Deployment Admin Dashboard
- **Cross-Group Management**: Oversight across all wheel groups
- **System Monitoring**: Health checks and performance metrics
- **User Management**: Create and manage deployment administrators
- **Resource Cleanup**: Automated maintenance and optimization
- **Security Auditing**: Access logs and compliance reporting

### Wheel Group Management
- **Organization Setup**: Create isolated wheel groups
- **Quota Management**: Configure resource limits per group
- **User Role Assignment**: Fine-grained permission control
- **Data Export/Import**: Backup and migration capabilities
- **Custom Branding**: Theme and appearance customization

### Multi-Tenant Security
- **Data Isolation**: Complete separation between wheel groups
- **Role-Based Access**: Granular permissions at multiple levels
- **Audit Trails**: Comprehensive logging of all operations
- **Secure APIs**: Authentication and authorization at every endpoint
- **Cross-Tenant Protection**: Zero data leakage guarantees

## V1 Administrative Features
- **Basic User Management**: Simple Cognito administration
- **Wheel Operations**: Standard create/edit/delete functionality
- **Participant Import**: CSV upload using utility script
- **Simple Monitoring**: Basic CloudFormation stack management

>>>>>>> 1d1196afb6e73e23c969e15bcc52370716a8caab
# 🔧 Administration & Maintenance

## V2 Administrative Features

### Deployment Admin Dashboard
- **Cross-Group Management**: Oversight across all wheel groups
- **System Monitoring**: Health checks and performance metrics
- **User Management**: Create and manage deployment administrators
- **Resource Cleanup**: Automated maintenance and optimization
- **Security Auditing**: Access logs and compliance reporting

### Wheel Group Management
- **Organization Setup**: Create isolated wheel groups
- **Quota Management**: Configure resource limits per group
- **User Role Assignment**: Fine-grained permission control
- **Data Export/Import**: Backup and migration capabilities
- **Custom Branding**: Theme and appearance customization

### Multi-Tenant Security
- **Data Isolation**: Complete separation between wheel groups
- **Role-Based Access**: Granular permissions at multiple levels
- **Audit Trails**: Comprehensive logging of all operations
- **Secure APIs**: Authentication and authorization at every endpoint
- **Cross-Tenant Protection**: Zero data leakage guarantees

## V1 Administrative Features
- **Basic User Management**: Simple Cognito administration
- **Wheel Operations**: Standard create/edit/delete functionality
- **Participant Import**: CSV upload using utility script
- **Simple Monitoring**: Basic CloudFormation stack management

=======
# 🔧 Administration & Maintenance

## V2 Administrative Features

### Deployment Admin Dashboard
- **Cross-Group Management**: Oversight across all wheel groups
- **System Monitoring**: Health checks and performance metrics
- **User Management**: Create and manage deployment administrators
- **Resource Cleanup**: Automated maintenance and optimization
- **Security Auditing**: Access logs and compliance reporting

### Wheel Group Management
- **Organization Setup**: Create isolated wheel groups
- **Quota Management**: Configure resource limits per group
- **User Role Assignment**: Fine-grained permission control
- **Data Export/Import**: Backup and migration capabilities
- **Custom Branding**: Theme and appearance customization

### Multi-Tenant Security
- **Data Isolation**: Complete separation between wheel groups
- **Role-Based Access**: Granular permissions at multiple levels
- **Audit Trails**: Comprehensive logging of all operations
- **Secure APIs**: Authentication and authorization at every endpoint
- **Cross-Tenant Protection**: Zero data leakage guarantees

## V1 Administrative Features
- **Basic User Management**: Simple Cognito administration
- **Wheel Operations**: Standard create/edit/delete functionality
- **Participant Import**: CSV upload using utility script
- **Simple Monitoring**: Basic CloudFormation stack management

>>>>>>> 1d1196afb6e73e23c969e15bcc52370716a8caab
# 📋 Miscellaneous

## Import Participant Data from CSV

### V1 Legacy CSV Import
Use the utility script for V1 deployments:
```bash
cd utils && python wheel_feeder.py \
  --wheel-url <https://your_api_gateway.amazonaws.com> \
  --wheel-id <TARGET_WHEEL_ID> \
  --csv-file-path <PATH_TO_CSV_FILE> \
  --cognito-user-pool-id <COGNITO_USER_POOL_ID> \
  --cognito-client-id <COGNITO_CLIENT_ID>
```

## Stack Management

### V2 Stack Operations
```bash
# List all V2 stacks
aws cloudformation list-stacks --query 'StackSummaries[?contains(StackName, `aws-ops-wheel-v2`)]'

# Delete V2 stack with cleanup
./deploy-v2.sh --delete --suffix <SUFFIX>

# Quick updates
./deploy-v2.sh --quick-update --suffix <SUFFIX>
```

### Wheel Customization
To change wheel spinning speed, modify `EASE_OUT_FRAMES` and `LINEAR_FRAMES` in `ui/src/components/wheel.jsx`. Lower values correspond to faster spinning.

---

## License & Legal

This project is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE), [`NOTICE`](NOTICE), and [`THIRD-PARTY-LICENSES`](THIRD-PARTY-LICENSES) for complete details.
