# Cron Jobs on WLS2

To run a cron job in Python on WSL2, you can use the Linux cron service to schedule and run your Python script automatically. Here's how to set it up:

## Step 1: Edit the Crontab

Open your WSL2 terminal (Ubuntu in WSL2). Type crontab -e to edit the cron jobs. If this is your first time using crontab, it might ask you to select an editor. Pick one you're comfortable with (usually, nano or vim).

## Step 2: Add Your Cron Job

In the crontab file, specify the schedule and command to run your Python script. The syntax is as follows:

```bash
* * * * * /path/to/python3 /path/to/your_script.py >> /path/to/logfile.log 2>&1
```

Each * represents a unit of time in the following order: minute hour day month day-of-week

**For example:**

*/5 * * * * – Run every 5 minutes.

0 12 * * * – Run every day at 12:00 noon.

Here’s a sample entry to run your_script.py every 5 minutes:

```bash
*/5 * * * * /usr/bin/python3 /home/username/path/to/your_script.py >> /home/username/path/to/cron.log 2>&1
```

## Step 3: Ensure the Cron Service is Running

To check if cron is running, use:

```bash
sudo service cron status
```

If it’s not running, start it with:

```bash
sudo service cron start
```

To ensure cron starts automatically when you start WSL2, you can add sudo service cron start to your WSL startup file (like .bashrc or .profile).

## Step 4: Check Cron Logs

If you want to confirm that your cron job is running, you can check the logs for any output or errors:

```bash
cat /var/log/syslog | grep CRON
```

Or look at the custom log file you specified (cron.log in the example) for output and errors from the script.
