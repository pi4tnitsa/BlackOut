#!/bin/bash

# Nuclei Worker Setup Script
# This script is deployed and executed on worker servers

set -e

echo "========================================="
echo "   Nuclei Worker Setup"
echo "========================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run this script with sudo${NC}"
    exit 1
fi

# Update system
echo -e "${YELLOW}[1/5] Updating system packages...${NC}"
apt-get update

# Install dependencies
echo -e "${YELLOW}[2/5] Installing dependencies...${NC}"
apt-get install -y screen unzip unrar curl git jq

# Install Nuclei
echo -e "${YELLOW}[3/5] Installing Nuclei...${NC}"
# Get latest version
LATEST_VERSION=$(curl -s https://api.github.com/repos/projectdiscovery/nuclei/releases/latest | jq -r '.tag_name')
echo "Installing Nuclei ${LATEST_VERSION}..."

# Download and install
curl -sL "https://github.com/projectdiscovery/nuclei/releases/download/${LATEST_VERSION}/nuclei_$(echo ${LATEST_VERSION} | sed 's/v//')_linux_amd64.zip" -o nuclei.zip
unzip -o nuclei.zip
chmod +x nuclei
mv nuclei /usr/local/bin/
rm nuclei.zip

# Verify installation
nuclei -version

# Create working directories
echo -e "${YELLOW}[4/5] Creating working directories...${NC}"
mkdir -p /home/$SUDO_USER/nuclei-worker/{templates,targets,results,logs}
chown -R $SUDO_USER:$SUDO_USER /home/$SUDO_USER/nuclei-worker

# Create run script
echo -e "${YELLOW}[5/5] Creating run script...${NC}"
cat > /home/$SUDO_USER/nuclei-worker/run_scan.sh << 'EOF'
#!/bin/bash

# Nuclei scan runner script
TASK_ID=$1
TEMPLATE_PATH=$2
TARGETS_PATH=$3
OUTPUT_PATH=$4
LOG_PATH="/home/$USER/nuclei-worker/logs/nuclei_task_${TASK_ID}.log"

echo "Starting Nuclei scan for task ${TASK_ID}" | tee -a "$LOG_PATH"
echo "Template: ${TEMPLATE_PATH}" | tee -a "$LOG_PATH"
echo "Targets: ${TARGETS_PATH}" | tee -a "$LOG_PATH"
echo "Output: ${OUTPUT_PATH}" | tee -a "$LOG_PATH"
echo "===========================================" | tee -a "$LOG_PATH"

# Run nuclei with logging
nuclei \
    -t "$TEMPLATE_PATH" \
    -l "$TARGETS_PATH" \
    -o "$OUTPUT_PATH" \
    -json \
    -rate-limit 150 \
    -bulk-size 50 \
    -concurrency 50 \
    -stats \
    -silent \
    2>&1 | tee -a "$LOG_PATH"

echo "===========================================" | tee -a "$LOG_PATH"
echo "Scan completed for task ${TASK_ID}" | tee -a "$LOG_PATH"
echo "Results saved to: ${OUTPUT_PATH}" | tee -a "$LOG_PATH"
EOF

chmod +x /home/$SUDO_USER/nuclei-worker/run_scan.sh
chown $SUDO_USER:$SUDO_USER /home/$SUDO_USER/nuclei-worker/run_scan.sh

# Create cleanup script
cat > /home/$SUDO_USER/nuclei-worker/cleanup.sh << 'EOF'
#!/bin/bash

# Cleanup old logs and results (older than 7 days)
find /home/$USER/nuclei-worker/logs -name "*.log" -mtime +7 -delete
find /home/$USER/nuclei-worker/results -name "*.json" -mtime +7 -delete
find /home/$USER/nuclei-worker/targets -name "*.txt" -mtime +7 -delete
EOF

chmod +x /home/$SUDO_USER/nuclei-worker/cleanup.sh
chown $SUDO_USER:$SUDO_USER /home/$SUDO_USER/nuclei-worker/cleanup.sh

# Add cleanup to crontab (run daily at 3 AM)
(crontab -u $SUDO_USER -l 2>/dev/null; echo "0 3 * * * /home/$SUDO_USER/nuclei-worker/cleanup.sh") | crontab -u $SUDO_USER -

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Worker setup completed successfully!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo -e "Working directory: ${YELLOW}/home/$SUDO_USER/nuclei-worker${NC}"
echo -e "Run script: ${YELLOW}/home/$SUDO_USER/nuclei-worker/run_scan.sh${NC}"
echo -e "${GREEN}=========================================${NC}"