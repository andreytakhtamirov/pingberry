# Remove old zip
[ -f pingberry-env.zip ] && rm pingberry-env.zip

# Create temporary folder
mkdir pingberry-env

# Copy contents of client/ into pingberry-env/
cp -r client/* pingberry-env/

# Remove documentation/sample files
rm pingberry-env/app/mqtt_credentials.example.jsonc

# Zip the new folder
zip -r pingberry-env.zip pingberry-env

# Clean up
rm -r pingberry-env
