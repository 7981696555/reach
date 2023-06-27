import subprocess

# Step 1: Install gnupg
subprocess.run(['sudo', 'apt-get', 'install', 'gnupg'])

# Step 2: Download and install MongoDB public key
subprocess.run(['curl', '-fsSL', 'https://pgp.mongodb.com/server-6.0.asc', '|', 'sudo', 'gpg', '-o', '/usr/share/keyrings/mongodb-server-6.0.gpg', '--dearmor'])

# Step 3: Create the MongoDB list file
with open('/etc/apt/sources.list.d/mongodb-org-6.0.list', 'w') as f:
    f.write('deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse\n')

# Step 4: Add the MongoDB repository to apt-get
subprocess.run(['sudo', 'tee', '/etc/apt/sources.list.d/mongodb-org-6.0.list'], input=b"deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse\n", check=True)

# Step 5: Update apt-get
subprocess.run(['sudo', 'apt-get', 'update'])

# Step 6: Install MongoDB
subprocess.run(['sudo', 'apt-get', 'install', '-y', 'mongodb'])

# Step 7: Enable MongoDB on startup
subprocess.run(['sudo', 'systemctl', 'enable', 'mongodb'])

# Step 8: Start MongoDB
subprocess.run(['sudo', 'systemctl', 'start', 'mongodb'])

# Step 9: Reload the system daemon
subprocess.run(['sudo', 'systemctl', 'daemon-reload'])

# Step 10: Check the status of the MongoDB service
#subprocess.run(['sudo', 'systemctl', 'status', 'mongodb'])

# Step 11: Enable MongoDB on startup
subprocess.run(['sudo', 'systemctl', 'enable', 'mongodb'])

# Step 12: Run the MongoDB shell
#subprocess.run(['mongo'])
