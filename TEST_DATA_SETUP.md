# Test Data Setup Instructions

This guide helps you create test users and sample data for the multi-tenant AWS Ops Wheel system.

## Prerequisites

1. **Deploy the v2 infrastructure first:**
   ```bash
   ./deploy-v2-modular.sh
   ```

2. **Ensure AWS CLI is configured** with appropriate permissions for:
   - Cognito User Pool administration
   - DynamoDB table access
   - CloudFormation stack reading

## Quick Setup

### 1. Run the Setup Script
```bash
python3 setup_test_data.py
```

### 2. What Gets Created

**🏢 Tenant:**
- **ID:** `tenant-1`
- **Name:** `Test Company Inc`

**👥 Test Users:**
- **user1@test.com** (Role: USER) - Password: `TempPassword123!`
- **admin1@test.com** (Role: WHEEL_ADMIN) - Password: `TempPassword123!`  
- **superadmin@test.com** (Role: ADMIN) - Password: `TempPassword123!`

**🎯 Sample Wheels:**
- **Daily Standup Leader** (5 participants: Alice, Bob, Carol, David, Eve)
- **Code Review Assignments** (4 participants: Frontend, Backend, DevOps, QA teams)
- **Lunch Decision Maker** (6 participants: Pizza Palace, Burger Barn, etc.)

## Testing the Permission System

### Login as Different Users

1. **Regular User (user1@test.com):**
   - ✅ Can view wheels
   - ✅ Can spin wheels  
   - ❌ Cannot create/edit/delete wheels
   - ❌ Cannot manage participants

2. **Wheel Admin (admin1@test.com):**
   - ✅ Can view wheels
   - ✅ Can spin wheels
   - ✅ Can create/edit wheels
   - ✅ Can manage participants
   - ✅ Can delete wheels
   - ❌ Cannot manage users

3. **Super Admin (superadmin@test.com):**
   - ✅ Full access to everything
   - ✅ Future user management capabilities

### Expected UI Behavior

**USER Role:** Only sees "View" and "Spin" actions, no management buttons

**WHEEL_ADMIN Role:** Sees all wheel and participant management buttons

**ADMIN Role:** Sees everything including future admin panels

## Manual Configuration (if needed)

If the script fails, you can manually create users in the Cognito console:

### Cognito User Attributes Required:
```
email: user1@test.com
name: Regular User
custom:role: USER
custom:tenant_id: tenant-1
custom:tenant_name: Test Company Inc
```

### DynamoDB Records Required:
- **Users table:** user_id, email, name, tenant_id, role, status
- **Tenants table:** tenant_id, tenant_name, status, created_at
- **Wheels table:** tenant_wheel_id, wheel_name, description, created_by
- **Participants table:** tenant_wheel_participant_id, participant_name, weight

## Troubleshooting

### Script Errors
- **"Stack not found":** Run `./deploy-v2-modular.sh` first
- **"Access denied":** Check AWS CLI permissions
- **"User already exists":** Script will skip existing users safely

### Login Issues
- Ensure you're using the **ui-v2** frontend (not ui)
- Check browser console for authentication errors
- Verify Cognito User Pool configuration

### Permission Issues
- Check that custom attributes are set correctly in Cognito
- Verify JWT token contains the custom claims
- Check browser developer tools for 403 errors

## Clean Up

To remove test data:
1. Delete users from Cognito User Pool console
2. Delete records from DynamoDB tables manually
3. Or redeploy the entire stack to reset everything

---

✅ **You're now ready to test the multi-tenant permission system!**
