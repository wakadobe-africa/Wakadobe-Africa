# Production Email and Background Worker Setup Plan

## Goal
Make email delivery reliable in production by moving away from Gmail SMTP for live traffic and preparing the app for a real background worker.

## Recommended approach
Use a dedicated transactional mail provider such as SendGrid or Mailgun.

For this project, SendGrid is a strong default because it is straightforward to configure with SMTP or API credentials and works well on Render and Railway.

## What is already in place
The app already:
- reads mail settings from environment variables in [pkg/config.py](../pkg/config.py)
- routes email sending through task functions in [pkg/tasks.py](../pkg/tasks.py)
- calls those task functions from [pkg/token.py](../pkg/token.py)

That means the app is now prepared for the next layer: a real queue and worker process.

## Step 1: Choose and configure a production mail provider
Create an account with your provider and get these values:
- SMTP host
- SMTP port
- username
- password or API key
- verified sender address

### Recommended environment variables
Add these to your local `.env` file and to the deployment platform environment settings:

```env
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=apikey
MAIL_PASSWORD=your-sendgrid-api-key
MAIL_DEFAULT_SENDER=hello@yourdomain.com
```

### Why this matters
Gmail app passwords are fine for development, but they are not the best long-term option for production email delivery because they are more likely to be blocked or rate-limited by the provider.

## Step 2: Keep Gmail only for local testing
For local development you may still use Gmail, but for production use the provider above.

## Step 3: Add Redis and a worker runtime
The next production upgrade is to add:
- Redis as the job broker
- a worker process that consumes queued email jobs

### Suggested stack
- Redis
- RQ or Celery

This project already has task entrypoints, so the remaining work is to connect them to a queue backend.

## Step 4: Worker rollout plan
1. Provision Redis on Render or Railway, or use a managed Redis service.
2. Add the Redis URL to environment variables.
3. Create a worker entrypoint that uses the task module.
4. Start one web process and one worker process in deployment.

### Example environment variables
```env
REDIS_URL=redis://localhost:6379/0
```

## Step 5: Test the flow end to end
After setup:
1. Start the app locally.
2. Trigger a signup or password reset flow.
3. Confirm the email is delivered.
4. Check logs for any SMTP or queue errors.

## Step 6: Production deployment checklist
Before going live, verify:
- the sender address is verified
- the SMTP credentials are correct
- the app uses `MAIL_DEFAULT_SENDER`
- the worker process is running
- Redis is reachable from the worker
- logs show successful task execution

## Suggested implementation order
1. Configure SendGrid or Mailgun
2. Add environment variables for production
3. Add Redis and queue worker support
4. Test signup and password reset emails
5. Monitor logs and retry failures

## Practical note
The current code is already prepared for the first part of this journey. The next important step is not only mail configuration, but also making sure the worker process is running separately from the web process.
