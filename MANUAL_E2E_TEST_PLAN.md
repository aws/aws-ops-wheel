# AWS Ops Wheel v2 - Manual End-to-End Test Plan

## Test Environment Information
- **Frontend URL**: https://dlc44g0pisqep.cloudfront.net/app
- **API Base URL**: https://1b21uno1w8.execute-api.us-west-2.amazonaws.com/dev
- **Admin Credentials**: Username: `admin`, Password: `TempPass123!dev`
- **Test Date**: _____________
- **Tester**: _____________

---

## 🧪 **TEST SUITE 1: Public Wheel Group Creation (CRITICAL)**

### Test 1.1: Create New Public Wheel Group via Frontend
**Objective**: Verify the wheel group creation that was just fixed

**Steps**:
1. Navigate to: https://dlc44g0pisqep.cloudfront.net/app
2. Look for "Create Public Wheel Group" option or navigation
3. Fill out the form with:
   - **Wheel Group Name**: `E2E Test Group`
   - **Description**: `End-to-end test wheel group`
   - **Admin Username**: `e2eadmin`
   - **Admin Email**: `test+e2e@example.com` 
   - **Admin Password**: `TestPass123!`
4. Submit the form

**Expected Result**: 
- ✅ Success message appears
- ✅ New wheel group is created with proper JSON response
- ✅ NO "Unexpected token" or HTML error messages
- ✅ Proper wheel group data returned

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

### Test 1.2: Verify API Direct Call
**Objective**: Test the API endpoint directly

**Steps**:
1. Open terminal/command line
2. Run this curl command:
```bash
curl -X POST "https://1b21uno1w8.execute-api.us-west-2.amazonaws.com/dev/app/api/v2/wheel-group/create-public" \
  -H "Content-Type: application/json" \
  -d '{"wheel_group_name": "API Test Group", "description": "Direct API test", "admin_user": {"username": "apitest", "email": "apitest@example.com", "password": "ApiTest123!"}}'
```

**Expected Result**: 
- ✅ Returns JSON response with wheel group details
- ✅ Status includes wheel_group_id, created_at, admin_user info
- ✅ NO HTML doctype error

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

---

## 🔐 **TEST SUITE 2: Authentication & Login**

### Test 2.1: Admin Login
**Objective**: Verify admin authentication works

**Steps**:
1. Navigate to: https://dlc44g0pisqep.cloudfront.net/app
2. If not logged in, find Login button/link
3. Enter credentials:
   - **Username**: `admin`
   - **Password**: `TempPass123!dev`
4. Click Login

**Expected Result**: 
- ✅ Successfully logs in
- ✅ Redirected to admin dashboard
- ✅ Can see deployment admin navigation options

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

### Test 2.2: Regular User Login (if available)
**Objective**: Test regular user authentication

**Steps**:
1. If you have a regular user account, try logging in
2. Or create one via wheel group creation first
3. Login with regular user credentials

**Expected Result**: 
- ✅ Successfully logs in
- ✅ Sees appropriate user interface (not admin)
- ✅ Proper permissions applied

**Status**: ☐ PASS ☐ FAIL ☐ N/A
**Notes**: ________________________________

---

## 🔑 **TEST SUITE 3: Password Reset (RECENTLY FIXED)**

### Test 3.1: Forgot Password Flow
**Objective**: Test the password reset that was just improved

**Steps**:
1. Navigate to login page
2. Click "Forgot Password" link
3. Enter a valid username (e.g., `admin`)
4. Submit request
5. Check for success message

**Expected Result**: 
- ✅ Success message appears
- ✅ No JavaScript errors in browser console
- ✅ User directed to enter verification code

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

### Test 3.2: Email Delivery Check
**Objective**: Verify password reset emails are sent

**Steps**:
1. After requesting password reset
2. Wait 2-3 minutes
3. Check email inbox for the account
4. Look in spam folder if not in inbox

**Expected Result**: 
- ⚠️ Email may take time due to COGNITO_DEFAULT limits
- ✅ Email has subject "AWS Ops Wheel - Password Reset Code"
- ✅ Contains 6-digit verification code
- ✅ Includes expiration notice

**Status**: ☐ PASS ☐ FAIL ☐ EMAIL_NOT_RECEIVED
**Notes**: ________________________________

---

## 🎯 **TEST SUITE 4: Wheel Management**

### Test 4.1: Create New Wheel
**Objective**: Test wheel creation within a wheel group

**Steps**:
1. Login as admin or wheel group admin
2. Navigate to wheels section
3. Click "Create New Wheel"
4. Fill out form:
   - **Wheel Name**: `E2E Test Wheel`
   - **Description**: `End-to-end test wheel`
5. Submit

**Expected Result**: 
- ✅ Wheel created successfully
- ✅ Appears in wheel list
- ✅ Proper JSON response

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

### Test 4.2: Add Participants to Wheel
**Objective**: Test participant management

**Steps**:
1. Open the wheel created in Test 4.1
2. Click "Add Participant" or similar
3. Add participant:
   - **Name**: `Test Participant 1`
   - **Email**: `participant1@example.com`
4. Add another participant:
   - **Name**: `Test Participant 2`
   - **Email**: `participant2@example.com`

**Expected Result**: 
- ✅ Participants added successfully
- ✅ Show up in participant list
- ✅ Proper display formatting

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

### Test 4.3: Spin the Wheel
**Objective**: Test wheel spinning functionality

**Steps**:
1. With participants added, find "Spin Wheel" button
2. Click to spin the wheel
3. Observe animation and result

**Expected Result**: 
- ✅ Wheel spins with animation
- ✅ Selects a participant randomly
- ✅ Shows clear winner
- ✅ Updates participant selection history

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

---

## 👥 **TEST SUITE 5: User Management (Admin Only)**

### Test 5.1: View All Wheel Groups
**Objective**: Test admin wheel group overview

**Steps**:
1. Login as admin
2. Navigate to wheel groups management
3. View list of all wheel groups

**Expected Result**: 
- ✅ Can see all wheel groups
- ✅ Shows group details (name, description, created date)
- ✅ Admin controls available

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

### Test 5.2: Manage Users Within Wheel Group
**Objective**: Test user management capabilities

**Steps**:
1. Select a wheel group
2. View users in that group
3. Try to add/remove users (if functionality exists)

**Expected Result**: 
- ✅ Can view users in wheel group
- ✅ User management functions work as expected
- ✅ Proper permission handling

**Status**: ☐ PASS ☐ FAIL ☐ N/A
**Notes**: ________________________________

---

## 🌐 **TEST SUITE 6: Browser Compatibility**

### Test 6.1: Chrome Browser
**Objective**: Verify functionality in Chrome

**Steps**:
1. Open Google Chrome
2. Navigate to application
3. Run through key functions (login, create wheel group, spin wheel)

**Expected Result**: 
- ✅ All functions work properly
- ✅ No console errors
- ✅ UI displays correctly

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

### Test 6.2: Safari Browser (if available)
**Objective**: Test Safari compatibility

**Steps**:
1. Open Safari
2. Navigate to application
3. Test core functionality

**Expected Result**: 
- ✅ Application loads and functions
- ✅ Authentication works
- ✅ Basic operations successful

**Status**: ☐ PASS ☐ FAIL ☐ N/A
**Notes**: ________________________________

---

## 📱 **TEST SUITE 7: Mobile Responsiveness**

### Test 7.1: Mobile Browser Test
**Objective**: Verify mobile functionality

**Steps**:
1. Open application on mobile device or use browser dev tools mobile view
2. Test navigation and key functions
3. Verify UI adapts to screen size

**Expected Result**: 
- ✅ UI is responsive
- ✅ Navigation works on mobile
- ✅ Key functions accessible

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

---

## 🔍 **TEST SUITE 8: Error Handling**

### Test 8.1: Invalid Login Attempt
**Objective**: Test error handling for authentication

**Steps**:
1. Try to login with invalid credentials
2. Username: `invalid`, Password: `wrong`

**Expected Result**: 
- ✅ Clear error message displayed
- ✅ No application crash
- ✅ User can retry login

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

### Test 8.2: Network Error Simulation
**Objective**: Test offline/network error handling

**Steps**:
1. Disconnect internet (or use browser dev tools to simulate)
2. Try to perform an action
3. Reconnect and retry

**Expected Result**: 
- ✅ Graceful error handling
- ✅ User-friendly error messages
- ✅ Recovery possible when connection restored

**Status**: ☐ PASS ☐ FAIL
**Notes**: ________________________________

---

## 📊 **TEST RESULTS SUMMARY**

### Critical Tests (Must Pass):
- [ ] Test 1.1: Public Wheel Group Creation
- [ ] Test 1.2: API Direct Call  
- [ ] Test 2.1: Admin Login
- [ ] Test 4.3: Spin the Wheel

### Important Tests:
- [ ] Test 3.1: Forgot Password Flow
- [ ] Test 4.1: Create New Wheel
- [ ] Test 4.2: Add Participants

### Nice-to-Have Tests:
- [ ] Test 6.x: Browser Compatibility
- [ ] Test 7.1: Mobile Responsiveness
- [ ] Test 8.x: Error Handling

### Overall Status: ☐ PASS ☐ FAIL ☐ PARTIAL

### Notes & Issues Found:
_________________________________________________
_________________________________________________
_________________________________________________

### Recommendations:
_________________________________________________
_________________________________________________
_________________________________________________

---

**Test Completed By**: _________________ **Date**: _________________
