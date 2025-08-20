# 🔒 Git Backup Commands for BOM2Pic

## Phase 1: Backup Current Working State

```bash
# Navigate to project
cd /Users/gilraz/Projects/BOM2Pic

# Add all current changes
git add .

# Commit working state
git commit -m "🔒 WORKING STATE: PayPal integration functional

✅ PayPal API working (sandbox)
✅ Plans configured: $9/$29/$49
✅ Security fixed: New Supabase keys
✅ Frontend working: UI, auth, processing
✅ API endpoints: /health, /api/plans, /process

🔧 Known issues to fix separately:
- Magic link emails not sending
- Usage limits not enforced

This commit represents a stable, revenue-ready state."

# Create safety tag
git tag v1.0-paypal-working

# Push everything to remote
git push origin main --tags
```

## Phase 2: Create Feature Branches

```bash
# Create branch for authentication fixes
git checkout -b feature/auth-fixes
git push -u origin feature/auth-fixes

# Create branch for usage limit fixes  
git checkout -b feature/usage-limits
git push -u origin feature/usage-limits

# Return to main branch
git checkout main
```

## Phase 3: Development Workflow

```bash
# Work on auth fixes
git checkout feature/auth-fixes
# ... make changes ...
git add .
git commit -m "Fix magic link email configuration"

# Work on usage limits
git checkout feature/usage-limits  
# ... make changes ...
git add .
git commit -m "Implement usage quota enforcement"

# Merge when ready (after testing)
git checkout main
git merge feature/auth-fixes
git merge feature/usage-limits
```

## Emergency Rollback

```bash
# If anything breaks, rollback to working state
git checkout main
git reset --hard v1.0-paypal-working
git push --force-with-lease origin main
```

---

**🚨 CRITICAL: Run these commands in Terminal to secure your working code!**
