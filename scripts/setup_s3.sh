#!/bin/bash
# Selectel S3 Setup Helper
# Based on instructions from: https://docs.selectel.ru/storage/s3/tools/aws-cli/

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

PROFILE_NAME="ru-3"
REGION="ru-3"
ENDPOINT="https://s3.ru-3.storage.selcloud.ru"

echo -e "${GREEN}Selectel S3 Setup Script for S•NOVA AI${NC}"
echo "------------------------------------------"

# 1. AWS CLI Check
if ! command -v aws &> /dev/null
then
    echo "AWS CLI not found. Please install it: sudo apt install awscli"
    exit 1
fi

# 2. Configure AWS Profile
echo "Step 1: Configuring AWS Profile '$PROFILE_NAME'..."
echo "Please enter your Access Key and Secret Key when prompted."
aws configure --profile $PROFILE_NAME

# 3. Update AWS Config with Endpoint
CONFIG_FILE="$HOME/.aws/config"
if [ ! -f "$CONFIG_FILE" ]; then
    mkdir -p "$HOME/.aws"
    touch "$CONFIG_FILE"
fi

if ! grep -q "\[profile $PROFILE_NAME\]" "$CONFIG_FILE"; then
    echo -e "\n[profile $PROFILE_NAME]\nregion = $REGION\nendpoint_url = $ENDPOINT" >> "$CONFIG_FILE"
    echo "Added endpoint_url to $CONFIG_FILE"
else
    echo "Profile '$PROFILE_NAME' already exists in $CONFIG_FILE. Please verify endpoint manually."
fi

# 4. Handle SSL Certificate (GlobalSign Root R6)
echo -e "\nStep 2: Downloading and setting up SSL Certificate..."
CERT_DIR="$HOME/.snova-ai"
mkdir -p "$CERT_DIR"
wget -q https://secure.globalsign.net/cacert/root-r6.crt -O "$CERT_DIR/root.der"

if command -v openssl &> /dev/null; then
    openssl x509 -inform der -in "$CERT_DIR/root.der" -out "$CERT_DIR/root.crt"
    chmod 600 "$CERT_DIR/root.crt"
    echo "Certificate converted to PEM and saved to $CERT_DIR/root.crt"
    
    # Add ca_bundle to config if not present
    if ! grep -q "ca_bundle" "$CONFIG_FILE"; then
        # Insert after the profile definition
        sed -i "/\[profile $PROFILE_NAME\]/a ca_bundle = $CERT_DIR/root.crt" "$CONFIG_FILE"
        echo "Added ca_bundle to $CONFIG_FILE"
    fi
else
    echo "Warning: openssl not found. Could not convert DER to PEM. Python backend handles this automatically if certs/root.crt exists in project."
fi

echo -e "\n${GREEN}Setup complete!${NC}"
echo "Test your connection with: aws --profile $PROFILE_NAME s3 ls"
