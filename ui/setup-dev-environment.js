#!/usr/bin/env node

/*
 * Setup Development Environment
 * 
 * This script automatically detects your deployed AWS Ops Wheel CloudFront domain
 * and configures the local development environment to connect to it.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function findCloudFrontDomain() {
  try {
    console.log('🔍 Looking for AWS Ops Wheel deployments...');
    
    // First, check if we have any AWSOpsWheel stacks
    const stacks = execSync(`aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[?contains(StackName, \`AWSOpsWheel\`)].StackName' --output text`, { encoding: 'utf8' }).trim();
    
    if (!stacks) {
      console.error('❌ No AWS Ops Wheel deployments found.');
      console.log('   Please deploy the application first using: ./deploy.sh --email your@email.com');
      process.exit(1);
    }
    
    console.log('✅ Found AWS Ops Wheel deployment');
    
    // Look for CloudFront stack - could be with or without suffix
    const stackNames = stacks.split(/\s+/);
    const cloudFrontStack = stackNames.find(name => name.includes('CloudFront'));
    
    if (!cloudFrontStack) {
      console.error('❌ CloudFront stack not found.');
      console.log('   Available stacks:', stackNames.join(', '));
      console.log('   You may need to deploy with CloudFront using: ./deploy.sh --email your@email.com');
      process.exit(1);
    }
    
    console.log(`📡 Found CloudFront stack: ${cloudFrontStack}`);
    
    // Get the CloudFront domain name
    const domain = execSync(`aws cloudformation describe-stacks --stack-name ${cloudFrontStack} --query 'Stacks[0].Outputs[?OutputKey==\`CloudFrontDomainName\`].OutputValue' --output text`, { encoding: 'utf8' }).trim();
    
    if (!domain || domain === '') {
      console.error('❌ Could not retrieve CloudFront domain name');
      process.exit(1);
    }
    
    console.log(`🌐 Found CloudFront domain: https://${domain}`);
    return `https://${domain}`;
    
  } catch (error) {
    console.error('❌ Error detecting deployment:', error.message);
    console.log('\n💡 Troubleshooting:');
    console.log('   1. Make sure AWS CLI is configured: aws configure');
    console.log('   2. Ensure you have deployed the app: ./deploy.sh --email your@email.com');
    console.log('   3. Check your AWS permissions');
    process.exit(1);
  }
}

function updateDevelopmentConfig(domain) {
  const configPath = path.join(__dirname, 'development_app_location.js');
  const configContent = `module.exports = '${domain}';`;
  
  try {
    fs.writeFileSync(configPath, configContent);
    console.log(`✅ Updated ${configPath}`);
    console.log(`🚀 Local development now configured to use: ${domain}`);
  } catch (error) {
    console.error('❌ Error updating development config:', error.message);
    process.exit(1);
  }
}

function main() {
  console.log('🎯 AWS Ops Wheel - Development Environment Setup\n');
  
  const domain = findCloudFrontDomain();
  updateDevelopmentConfig(domain);
  
  console.log('\n✨ Setup complete! You can now run:');
  console.log('   npm run start');
  console.log('\n📝 Note: Run this script again if you deploy to a different AWS account or region.');
}

if (require.main === module) {
  main();
}

module.exports = { findCloudFrontDomain, updateDevelopmentConfig };
