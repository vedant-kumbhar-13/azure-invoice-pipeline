# ══════════════════════════════════════════════════════════════
# InvoiceAI Frontend — Production Build Script
#
# BUG-C6: Documents the required steps to build for production.
# Run this from the frontend/ directory.
# ══════════════════════════════════════════════════════════════
#
# Usage (PowerShell / bash):
#
#   1. Set the API URL (required — no default exists in production):
#      $env:VITE_API_URL = "https://api.yourdomain.com"  # PowerShell
#      export VITE_API_URL="https://api.yourdomain.com"  # bash
#
#   2. Build:
#      npm run build
#
#   3. Serve the dist/ directory from your CDN / S3 / CloudFront.
#
# Or simply update VITE_API_URL in .env.production before building.
# The .env.production file is automatically loaded by Vite for production builds.
#
# CI/CD (GitHub Actions example):
#   - name: Build frontend
#     env:
#       VITE_API_URL: ${{ secrets.PRODUCTION_API_URL }}
#     run: npm run build
