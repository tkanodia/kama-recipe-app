#!/bin/bash
awslocal s3 mb s3://kama-uploads 2>/dev/null || true
echo "S3 bucket 'kama-uploads' ready."
