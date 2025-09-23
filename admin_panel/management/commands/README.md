# GupShup Admin Panel Management Commands

This directory contains management commands for the GupShup admin panel system. These commands provide essential functionality for managing the admin panel from the command line.

## Available Commands

### 1. `create_admin.py`
Creates new admin users with proper roles and permissions.

**Usage:**
```bash
# Interactive mode
python manage.py create_admin

# Non-interactive mode
python manage.py create_admin --username=admin --email=admin@example.com --password=SecurePass123! --role=admin --non-interactive

# Create super admin
python manage.py create_admin --super-admin --username=superadmin --email=super@example.com
```

**Options:**
- `--username`: Admin username
- `--email`: Admin email address
- `--password`: Admin password (not recommended for security)
- `--role`: Admin role (super_admin, admin, moderator, support)
- `--full-name`: Admin full name
- `--department`: Admin department
- `--phone`: Admin phone number
- `--non-interactive`: Run without prompts
- `--super-admin`: Create super admin with all permissions

### 2. `cleanup_sessions.py`
Cleans up expired admin sessions and old audit logs.

**Usage:**
```bash
# Default cleanup (30 days sessions, 90 days audit logs)
python manage.py cleanup_sessions

# Custom retention periods
python manage.py cleanup_sessions --days=7 --audit-days=30

# Dry run to see what would be cleaned
python manage.py cleanup_sessions --dry-run

# Force cleanup without confirmation
python manage.py cleanup_sessions --force
```

**Options:**
- `--days`: Days to keep inactive sessions (default: 30)
- `--audit-days`: Days to keep audit logs (default: 90)
- `--dry-run`: Show what would be cleaned without deleting
- `--force`: Force cleanup without confirmation

### 3. `generate_reports.py`
Generates various administrative reports.

**Usage:**
```bash
# Generate daily report
python manage.py generate_reports --type=daily

# Generate weekly report in JSON format
python manage.py generate_reports --type=weekly --format=json --output=reports/weekly.json

# Generate user summary and email it
python manage.py generate_reports --type=user-summary --email=admin@example.com

# Generate custom date range report
python manage.py generate_reports --type=monthly --start-date=2024-01-01 --end-date=2024-01-31
```

**Options:**
- `--type`: Report type (daily, weekly, monthly, user-summary, content-summary, moderation-summary)
- `--format`: Output format (html, json, csv)
- `--output`: Save report to file
- `--start-date`: Start date (YYYY-MM-DD)
- `--end-date`: End date (YYYY-MM-DD)
- `--email`: Email report to address
- `--quiet`: Suppress console output

### 4. `moderate_content.py`
Batch content moderation operations.

**Usage:**
```bash
# Review recent content
python manage.py moderate_content --action=review --filter=recent

# Flag suspicious content
python manage.py moderate_content --action=flag --filter=suspicious --severity=high --admin=moderator1

# Analyze and auto-approve clean content
python manage.py moderate_content --action=analyze --auto-approve --content-type=both

# Dry run to see what would be processed
python manage.py moderate_content --action=delete --filter=flagged --dry-run
```

**Options:**
- `--action`: Moderation action (review, flag, approve, delete, analyze)
- `--filter`: Content filter (recent, flagged, reported, suspicious, all)
- `--content-type`: Content type (posts, comments, both)
- `--days`: Days to look back (default: 7)
- `--limit`: Maximum items to process (default: 100)
- `--admin`: Admin username performing moderation
- `--reason`: Reason for bulk action
- `--dry-run`: Show what would be done without changes
- `--auto-approve`: Auto-approve content that passes filters
- `--export`: Export results to file
- `--severity`: Severity level (low, medium, high, critical)

### 5. `reset_admin_password.py`
Resets admin user passwords with security features.

**Usage:**
```bash
# Interactive password reset
python manage.py reset_admin_password --username=admin_user

# Force reset with session expiration
python manage.py reset_admin_password --username=admin_user --force --expire-sessions

# Reset and deactivate account
python manage.py reset_admin_password --username=admin_user --deactivate
```

**Options:**
- `--username`: Username of admin to reset (required)
- `--password`: New password (not recommended for security)
- `--force`: Force reset without confirmation
- `--deactivate`: Deactivate account after reset
- `--expire-sessions`: Expire all existing sessions

## Security Considerations

1. **Password Security**: Never use `--password` option in production. Always use interactive mode.
2. **Audit Logging**: All commands log their actions for audit purposes.
3. **Confirmation**: Destructive operations require confirmation unless `--force` is used.
4. **Access Control**: Only users with appropriate system access should run these commands.

## Scheduling Commands

You can schedule these commands using cron jobs:

```bash
# Daily session cleanup at 2 AM
0 2 * * * cd /path/to/project && python manage.py cleanup_sessions

# Weekly reports on Sundays at 1 AM
0 1 * * 0 cd /path/to/project && python manage.py generate_reports --type=weekly --output=reports/weekly.html

# Daily content analysis
0 3 * * * cd /path/to/project && python manage.py moderate_content --action=analyze --auto-approve --quiet
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure you have proper database access and file permissions.
2. **Admin Not Found**: Verify the admin username exists in the AdminUser table.
3. **Email Issues**: Check Django email configuration for report emailing.
4. **Memory Issues**: Use `--limit` option for large datasets in moderation commands.

### Log Files

All command executions are logged in the AdminAction model. Check the admin panel audit logs for command execution history.

## Examples

### Initial Setup
```bash
# Create first super admin
python manage.py create_admin --super-admin --username=superadmin --email=admin@gupshup.com

# Set up weekly automated tasks
python manage.py cleanup_sessions --force
python manage.py generate_reports --type=weekly --output=reports/setup_report.html
```

### Regular Maintenance
```bash
# Weekly maintenance routine
python manage.py cleanup_sessions
python manage.py moderate_content --action=analyze --auto-approve
python manage.py generate_reports --type=weekly --email=admin@gupshup.com
```

### Emergency Procedures
```bash
# Emergency admin access
python manage.py reset_admin_password --username=emergency_admin --expire-sessions

# Mass content cleanup
python manage.py moderate_content --action=flag --filter=suspicious --severity=critical --admin=emergency_admin
```