#!/usr/bin/env python3
"""
SleepBetter CLI - Sleep debt tracker and recovery planner

A personal sleep tracking tool that helps monitor sleep patterns, calculate sleep debt,
and provide science-based recommendations for recovery.

Features:
- Track sleep with bedtime/wake time
- Calculate and visualize sleep debt progressively
- Generate graphical reports (auto-displayed)
- Personalized bedtime recommendations
- Plan recovery schedule based on sleep science

Author: Houman Khosravani MD PhD FRCPC
License: MIT
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
DATA_FILE = Path(__file__).parent / "sleep_data.json"
TARGET_SLEEP = 7.0  # hours - minimum recommended for age 45-54
OPTIMAL_SLEEP = 8.0  # hours - optimal for recovery
MAX_RECOVERY_PER_NIGHT = 1.5  # max extra sleep to recover debt per night
DEFAULT_WAKE_TIME = 6.75  # 6:45 AM in decimal hours

# ANSI colors for terminal output
class Colors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'

def load_data():
    """Load sleep data from JSON file."""
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"entries": [], "profile": {"age": 35, "target": TARGET_SLEEP, "wake_time": DEFAULT_WAKE_TIME}}

def save_data(data):
    """Save sleep data to JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def hours_to_hm(hours):
    """Convert decimal hours to h:mm format."""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}:{m:02d}"

def hm_to_hours(hm_str):
    """Convert h:mm or decimal string to decimal hours."""
    if ':' in hm_str:
        parts = hm_str.split(':')
        return float(parts[0]) + float(parts[1]) / 60
    return float(hm_str)

def time_to_decimal(time_str):
    """Convert HH:MM time to decimal hours from midnight."""
    parts = time_str.split(':')
    return float(parts[0]) + float(parts[1]) / 60

def decimal_to_time(decimal):
    """Convert decimal hours to HH:MM format."""
    # Handle negative times (evening before midnight)
    if decimal < 0:
        decimal += 24
    h = int(decimal) % 24
    m = int((decimal - int(decimal)) * 60)
    return f"{h:02d}:{m:02d}"

def get_color_for_sleep(hours):
    """Return color based on sleep duration."""
    if hours >= 7.0:
        return Colors.GREEN
    elif hours >= 6.0:
        return Colors.YELLOW
    else:
        return Colors.RED

def calculate_debt(entries, target=TARGET_SLEEP):
    """Calculate cumulative sleep debt."""
    total_deficit = 0
    for entry in entries:
        deficit = target - entry['hours']
        total_deficit += deficit
    return total_deficit

def get_missing_days(entries):
    """
    Find days between last entry and yesterday that have no sleep data.
    Today is excluded because sleep hasn't happened yet.
    """
    if not entries:
        return []

    entries_sorted = sorted(entries, key=lambda x: x['date'])
    last_date = datetime.strptime(entries_sorted[-1]['date'], '%Y-%m-%d')
    yesterday = datetime.now() - timedelta(days=1)

    # Only look for missing days up to yesterday (not today)
    if last_date >= yesterday:
        return []

    missing = []
    current = last_date + timedelta(days=1)

    while current <= yesterday:
        date_str = current.strftime('%Y-%m-%d')
        if not any(e['date'] == date_str for e in entries):
            missing.append(date_str)
        current += timedelta(days=1)

    return missing


def calculate_progressive_debt(entries, target=TARGET_SLEEP):
    """Calculate sleep debt progression over time."""
    entries_sorted = sorted(entries, key=lambda x: x['date'])
    progressive = []
    cumulative_debt = 0

    for entry in entries_sorted:
        deficit = target - entry['hours']
        cumulative_debt += deficit
        progressive.append({
            'date': entry['date'],
            'hours': entry['hours'],
            'daily_deficit': deficit,
            'cumulative_debt': cumulative_debt
        })

    return progressive

def calculate_recommended_bedtime(target_sleep, wake_time=DEFAULT_WAKE_TIME, buffer_minutes=15):
    """
    Calculate recommended bedtime based on target sleep and wake time.
    Adds buffer for sleep onset latency (time to fall asleep).
    """
    # Sleep onset latency: typically 10-20 minutes
    total_time_needed = target_sleep + (buffer_minutes / 60)
    bedtime = wake_time - total_time_needed
    if bedtime < 0:
        bedtime += 24  # Wrap to previous day
    return bedtime

def get_sleep_recommendations(entries, current_debt):
    """
    Generate personalized sleep recommendations based on sleep science.
    """
    recommendations = []

    # Analyze recent patterns
    recent = entries[-7:] if len(entries) >= 7 else entries
    recent_avg = sum(e['hours'] for e in recent) / len(recent) if recent else 0

    # Get bedtime patterns if available
    entries_with_times = [e for e in recent if 'bedtime' in e]
    avg_bedtime = None
    if entries_with_times:
        avg_bedtime = sum(e['bedtime'] for e in entries_with_times) / len(entries_with_times)

    # Calculate recovery needs
    if current_debt > 0:
        # Sleep science: recover debt over 1-2 weeks, not all at once
        recovery_days = max(7, min(14, int(current_debt / 1.0)))  # ~1 hour extra per day max
        extra_per_night = min(current_debt / recovery_days, 1.5)  # Cap at 1.5h extra
        target_tonight = TARGET_SLEEP + extra_per_night

        # Calculate ideal bedtime for 6:45am wake
        ideal_bedtime = calculate_recommended_bedtime(target_tonight, DEFAULT_WAKE_TIME)

        recommendations.append({
            'priority': 'HIGH',
            'category': 'Sleep Duration',
            'action': f'Tonight: Aim for {hours_to_hm(target_tonight)} hours of sleep',
            'detail': f'You need {hours_to_hm(extra_per_night)} extra to start recovering your {hours_to_hm(current_debt)} debt'
        })

        recommendations.append({
            'priority': 'HIGH',
            'category': 'Bedtime',
            'action': f'Go to bed by {decimal_to_time(ideal_bedtime)}',
            'detail': f'For 6:45am wake with {hours_to_hm(target_tonight)} sleep (includes 15min to fall asleep)'
        })

    # Consistency recommendation
    if entries_with_times and len(entries_with_times) >= 3:
        bedtime_variance = max(e['bedtime'] for e in entries_with_times) - min(e['bedtime'] for e in entries_with_times)
        if bedtime_variance > 2:  # More than 2 hours variance
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Consistency',
                'action': 'Stabilize your bedtime',
                'detail': f'Your bedtime varies by {hours_to_hm(bedtime_variance)} hours. Aim for same time +/- 30min'
            })

    # Late bedtime warning
    if avg_bedtime and avg_bedtime > 0.5 and avg_bedtime < 12:  # After 12:30am
        recommendations.append({
            'priority': 'HIGH',
            'category': 'Circadian Rhythm',
            'action': 'Move bedtime earlier',
            'detail': f'Average bedtime {decimal_to_time(avg_bedtime)} is too late. Shift 15-30min earlier each night'
        })

    # Recovery-specific for high debt
    if current_debt > 10:
        recommendations.append({
            'priority': 'HIGH',
            'category': 'Recovery Protocol',
            'action': 'Prioritize weekend recovery',
            'detail': 'Sleep 9+ hours Sat/Sun. Naps OK but before 3pm and under 30min'
        })

        recommendations.append({
            'priority': 'MEDIUM',
            'category': 'Exercise',
            'action': 'Reduce training intensity',
            'detail': 'With significant debt, intense exercise increases injury/syncope risk. Light activity only.'
        })

    # General best practices
    recommendations.append({
        'priority': 'LOW',
        'category': 'Sleep Hygiene',
        'action': 'No screens 1 hour before bed',
        'detail': 'Blue light suppresses melatonin. Use night mode or blue-blocking glasses if needed.'
    })

    recommendations.append({
        'priority': 'LOW',
        'category': 'Caffeine',
        'action': 'No caffeine after 2:00 PM',
        'detail': 'Caffeine half-life is 5-6 hours. Late caffeine fragments sleep architecture.'
    })

    return recommendations

def open_image(filepath):
    """Open an image file in the default viewer (cross-platform)."""
    try:
        if sys.platform == 'darwin':  # macOS
            subprocess.Popen(['open', str(filepath)])
        elif sys.platform == 'win32':  # Windows
            os.startfile(str(filepath))
        else:  # Linux
            subprocess.Popen(['xdg-open', str(filepath)])
    except Exception as e:
        print(f"{Colors.YELLOW}Could not auto-open {filepath}: {e}{Colors.END}")

def cmd_status(args):
    """Show current sleep status and debt."""
    data = load_data()
    entries = data.get('entries', [])

    if not entries:
        print(f"{Colors.YELLOW}No sleep data recorded yet.{Colors.END}")
        print(f"Use: sleepbetter log <date> <hours:minutes>")
        return

    # Sort by date
    entries = sorted(entries, key=lambda x: x['date'])

    # Calculate statistics
    total_hours = sum(e['hours'] for e in entries)
    avg_sleep = total_hours / len(entries)
    debt = calculate_debt(entries)

    # Recent entries (last 7 days)
    recent = entries[-7:] if len(entries) >= 7 else entries
    recent_avg = sum(e['hours'] for e in recent) / len(recent)
    recent_debt = calculate_debt(recent)

    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  SLEEP STATUS REPORT{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

    # Overall stats
    print(f"{Colors.BOLD}Overall Statistics ({len(entries)} nights):{Colors.END}")
    print(f"  Average sleep:     {get_color_for_sleep(avg_sleep)}{hours_to_hm(avg_sleep)}{Colors.END} hours/night")
    print(f"  Target sleep:      {hours_to_hm(TARGET_SLEEP)} hours/night")
    print(f"  Total sleep debt:  {Colors.RED if debt > 0 else Colors.GREEN}{hours_to_hm(abs(debt))}{Colors.END} hours")

    print(f"\n{Colors.BOLD}Last 7 Nights:{Colors.END}")
    print(f"  Average:           {get_color_for_sleep(recent_avg)}{hours_to_hm(recent_avg)}{Colors.END} hours/night")
    print(f"  Week debt:         {Colors.RED if recent_debt > 0 else Colors.GREEN}{hours_to_hm(abs(recent_debt))}{Colors.END} hours")

    # Bedtime/wake stats if available
    entries_with_times = [e for e in entries if 'bedtime' in e and 'waketime' in e]
    if entries_with_times:
        avg_bedtime = sum(e['bedtime'] for e in entries_with_times) / len(entries_with_times)
        avg_waketime = sum(e['waketime'] for e in entries_with_times) / len(entries_with_times)
        print(f"\n{Colors.BOLD}Sleep Timing (avg):{Colors.END}")
        print(f"  Typical bedtime:   {Colors.MAGENTA}{decimal_to_time(avg_bedtime)}{Colors.END}")
        print(f"  Typical wake:      {Colors.BLUE}{decimal_to_time(avg_waketime)}{Colors.END}")

    # Recent sleep log
    print(f"\n{Colors.BOLD}Recent Sleep Log:{Colors.END}")
    has_times = any('bedtime' in e for e in entries[-10:])
    if has_times:
        print(f"  {Colors.DIM}{'Date':<12} {'Bed':>6} {'Wake':>6} {'Sleep':>6} {'Deficit':>8} {'Cum.Debt':>10}{Colors.END}")
        print(f"  {'-'*52}")
    else:
        print(f"  {Colors.DIM}{'Date':<12} {'Sleep':>8} {'Deficit':>10} {'Cum.Debt':>10}{Colors.END}")
        print(f"  {'-'*42}")

    # Calculate progressive debt for display
    progressive = calculate_progressive_debt(entries)
    recent_progressive = progressive[-10:]

    for prog in recent_progressive:
        entry = next(e for e in entries if e['date'] == prog['date'])
        hours = prog['hours']
        deficit = prog['daily_deficit']
        cum_debt = prog['cumulative_debt']

        color = get_color_for_sleep(hours)
        deficit_str = f"+{hours_to_hm(abs(deficit))}" if deficit < 0 else f"-{hours_to_hm(deficit)}"
        deficit_color = Colors.GREEN if deficit < 0 else Colors.RED
        debt_color = Colors.GREEN if cum_debt <= 0 else Colors.YELLOW if cum_debt < 7 else Colors.RED

        if has_times and 'bedtime' in entry:
            bed = decimal_to_time(entry.get('bedtime', 0))
            wake = decimal_to_time(entry.get('waketime', 0))
            print(f"  {entry['date']:<12} {Colors.MAGENTA}{bed:>6}{Colors.END} {Colors.BLUE}{wake:>6}{Colors.END} {color}{hours_to_hm(hours):>6}{Colors.END} {deficit_color}{deficit_str:>8}{Colors.END} {debt_color}{hours_to_hm(cum_debt):>10}{Colors.END}")
        else:
            print(f"  {entry['date']:<12} {color}{hours_to_hm(hours):>8}{Colors.END} {deficit_color}{deficit_str:>10}{Colors.END} {debt_color}{hours_to_hm(cum_debt):>10}{Colors.END}")

    # Warning if significant debt
    if debt > 10:
        print(f"\n{Colors.RED}{Colors.BOLD}WARNING: Significant sleep debt detected!{Colors.END}")
        print(f"{Colors.RED}Consider prioritizing sleep recovery to prevent health events.{Colors.END}")

    print()

def cmd_log(args):
    """Log sleep for a specific date - simple format: log <date> <hours:minutes>"""
    data = load_data()

    # Parse date
    date_str = args.date
    if date_str.lower() == 'today':
        date = datetime.now().strftime('%Y-%m-%d')
    elif date_str.lower() == 'yesterday':
        date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    elif len(date_str) == 5 and '-' in date_str:  # MM-DD format
        date = f"2025-{date_str}"  # Assume current year
    else:
        date = date_str  # Assume full YYYY-MM-DD

    # Parse hours
    hours = hm_to_hours(args.hours)

    # Calculate bedtime from wake time (default 6:45am)
    wake_time = data.get('profile', {}).get('wake_time', DEFAULT_WAKE_TIME)
    bedtime = wake_time - hours
    if bedtime < 0:
        bedtime += 24

    # Build entry
    entry = {
        'date': date,
        'hours': hours,
        'bedtime': bedtime,
        'waketime': wake_time
    }

    # Check if entry exists for this date
    entries = data.get('entries', [])
    existing = next((i for i, e in enumerate(entries) if e['date'] == date), None)

    if existing is not None:
        entries[existing] = entry
        action = "Updated"
    else:
        entries.append(entry)
        action = "Added"

    data['entries'] = sorted(entries, key=lambda x: x['date'])
    save_data(data)

    # Calculate debt
    debt = calculate_debt(data['entries'])

    color = get_color_for_sleep(hours)
    deficit = TARGET_SLEEP - hours

    print(f"\n{Colors.GREEN}{action}:{Colors.END} {date} - {color}{hours_to_hm(hours)}{Colors.END} hours")
    print(f"  Est. bedtime: {Colors.MAGENTA}{decimal_to_time(bedtime)}{Colors.END} → wake {Colors.BLUE}{decimal_to_time(wake_time)}{Colors.END}")

    if deficit > 0:
        print(f"  Daily deficit: {Colors.RED}-{hours_to_hm(deficit)}{Colors.END}")
    else:
        print(f"  Daily surplus: {Colors.GREEN}+{hours_to_hm(abs(deficit))}{Colors.END}")

    print(f"  Total sleep debt: {Colors.RED if debt > 0 else Colors.GREEN}{hours_to_hm(abs(debt))}{Colors.END} hours")

    # Show recommendation
    print(f"\n{Colors.BOLD}Tonight's Recommendation:{Colors.END}")
    if debt > 0:
        extra_needed = min(debt / 7, 1.5)  # Spread over week, cap at 1.5h
        target_tonight = TARGET_SLEEP + extra_needed
        ideal_bedtime = calculate_recommended_bedtime(target_tonight, wake_time)
        print(f"  Target: {Colors.GREEN}{hours_to_hm(target_tonight)}{Colors.END} hours")
        print(f"  Bedtime: {Colors.MAGENTA}{decimal_to_time(ideal_bedtime)}{Colors.END} for 6:45am wake")
    else:
        print(f"  {Colors.GREEN}Maintain 7+ hours. Great job!{Colors.END}")

    print()

def cmd_add(args):
    """Add a sleep entry interactively or via arguments."""
    data = load_data()

    # Interactive mode if no hours provided
    if not args.hours:
        print(f"\n{Colors.BOLD}{Colors.CYAN}Add Sleep Entry{Colors.END}\n")

        # Date
        default_date = datetime.now().strftime('%Y-%m-%d')
        date_input = input(f"Date [{default_date}]: ").strip()
        date = date_input if date_input else default_date

        # Bedtime
        bedtime_input = input("Bedtime (HH:MM, e.g., 23:30): ").strip()
        bedtime = time_to_decimal(bedtime_input) if bedtime_input else None

        # Wake time
        waketime_input = input(f"Wake time (HH:MM) [{decimal_to_time(DEFAULT_WAKE_TIME)}]: ").strip()
        waketime = time_to_decimal(waketime_input) if waketime_input else DEFAULT_WAKE_TIME

        # Calculate or ask for duration
        if bedtime is not None:
            # Calculate duration accounting for overnight sleep
            if waketime < bedtime:
                hours = (24 - bedtime) + waketime
            else:
                hours = waketime - bedtime
            print(f"Calculated sleep: {Colors.GREEN}{hours_to_hm(hours)}{Colors.END} hours")
            confirm = input("Correct? [Y/n]: ").strip().lower()
            if confirm == 'n':
                hours_input = input("Enter actual hours (h:mm or decimal): ").strip()
                hours = hm_to_hours(hours_input)
        else:
            hours_input = input("Total sleep (h:mm or decimal, e.g., 7:30 or 7.5): ").strip()
            hours = hm_to_hours(hours_input)
            # Estimate bedtime from hours and wake time
            bedtime = waketime - hours
            if bedtime < 0:
                bedtime += 24
    else:
        hours = hm_to_hours(args.hours)
        date = args.date or datetime.now().strftime('%Y-%m-%d')
        bedtime = time_to_decimal(args.bedtime) if args.bedtime else None
        waketime = time_to_decimal(args.waketime) if args.waketime else DEFAULT_WAKE_TIME

        if bedtime is None:
            bedtime = waketime - hours
            if bedtime < 0:
                bedtime += 24

    # Build entry
    entry = {'date': date, 'hours': hours, 'bedtime': bedtime, 'waketime': waketime}

    # Check if entry exists for this date
    entries = data.get('entries', [])
    existing = next((i for i, e in enumerate(entries) if e['date'] == date), None)

    if existing is not None:
        entries[existing] = entry
        action = "Updated"
    else:
        entries.append(entry)
        action = "Added"

    data['entries'] = sorted(entries, key=lambda x: x['date'])
    save_data(data)

    color = get_color_for_sleep(hours)
    deficit = TARGET_SLEEP - hours
    print(f"\n{Colors.GREEN}{action} sleep entry:{Colors.END} {date} - {color}{hours_to_hm(hours)}{Colors.END} hours")
    if deficit > 0:
        print(f"{Colors.YELLOW}Deficit: {hours_to_hm(deficit)} hours below target{Colors.END}")
    else:
        print(f"{Colors.GREEN}Surplus: {hours_to_hm(abs(deficit))} hours above target{Colors.END}")

    # Show updated debt
    debt = calculate_debt(data['entries'])
    print(f"Total sleep debt: {Colors.RED if debt > 0 else Colors.GREEN}{hours_to_hm(abs(debt))}{Colors.END} hours\n")

def cmd_recommend(args):
    """Show personalized sleep recommendations."""
    data = load_data()
    entries = data.get('entries', [])

    if not entries:
        print(f"{Colors.YELLOW}No sleep data. Add some entries first.{Colors.END}")
        return

    entries = sorted(entries, key=lambda x: x['date'])
    debt = calculate_debt(entries)

    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  PERSONALIZED SLEEP RECOMMENDATIONS{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

    print(f"{Colors.BOLD}Current Status:{Colors.END}")
    print(f"  Sleep debt: {Colors.RED if debt > 0 else Colors.GREEN}{hours_to_hm(abs(debt))}{Colors.END} hours")
    print(f"  Wake time: {Colors.BLUE}06:45{Colors.END} (configured)\n")

    recommendations = get_sleep_recommendations(entries, debt)

    # Group by priority
    for priority in ['HIGH', 'MEDIUM', 'LOW']:
        priority_recs = [r for r in recommendations if r['priority'] == priority]
        if not priority_recs:
            continue

        if priority == 'HIGH':
            color = Colors.RED
            symbol = '!'
        elif priority == 'MEDIUM':
            color = Colors.YELLOW
            symbol = '~'
        else:
            color = Colors.DIM
            symbol = '-'

        print(f"{color}{Colors.BOLD}[{priority} PRIORITY]{Colors.END}")
        for rec in priority_recs:
            print(f"  {color}{symbol}{Colors.END} {Colors.BOLD}{rec['action']}{Colors.END}")
            print(f"    {Colors.DIM}{rec['detail']}{Colors.END}")
        print()

    # Tonight's specific plan
    if debt > 0:
        extra_needed = min(debt / 7, 1.5)
        target_tonight = TARGET_SLEEP + extra_needed
        ideal_bedtime = calculate_recommended_bedtime(target_tonight, DEFAULT_WAKE_TIME)

        print(f"{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}  TONIGHT'S PLAN{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")
        print(f"  {Colors.BOLD}Target sleep:{Colors.END}  {Colors.GREEN}{hours_to_hm(target_tonight)}{Colors.END} hours")
        print(f"  {Colors.BOLD}Bedtime:{Colors.END}       {Colors.MAGENTA}{decimal_to_time(ideal_bedtime)}{Colors.END}")
        print(f"  {Colors.BOLD}Wake time:{Colors.END}     {Colors.BLUE}06:45{Colors.END}")
        print(f"  {Colors.BOLD}Extra needed:{Colors.END}  {hours_to_hm(extra_needed)} hours beyond minimum")

        # Calculate days to recovery
        days_to_recover = int(debt / extra_needed) if extra_needed > 0 else 0
        print(f"\n  {Colors.DIM}Following this plan: debt cleared in ~{days_to_recover} days{Colors.END}")

    print()

def cmd_plan(args):
    """Show recovery plan for the next few weeks."""
    data = load_data()
    entries = data.get('entries', [])

    debt = calculate_debt(entries) if entries else 0
    weeks = args.weeks or 3

    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  SLEEP RECOVERY PLAN{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

    if debt <= 0:
        print(f"{Colors.GREEN}No sleep debt to recover! Keep maintaining {hours_to_hm(TARGET_SLEEP)}+ hours/night.{Colors.END}\n")
        return

    print(f"{Colors.BOLD}Current Status:{Colors.END}")
    print(f"  Sleep debt:        {Colors.RED}{hours_to_hm(debt)}{Colors.END} hours")
    print(f"  Wake time:         {Colors.BLUE}06:45{Colors.END} (your schedule)")
    print(f"  Recovery period:   {weeks} weeks")

    # Calculate recovery schedule
    days = weeks * 7
    daily_recovery = min(debt / days, MAX_RECOVERY_PER_NIGHT)
    daily_target = TARGET_SLEEP + daily_recovery
    actual_recovery_days = debt / daily_recovery if daily_recovery > 0 else 0

    # Calculate bedtime for target
    ideal_bedtime = calculate_recommended_bedtime(daily_target, DEFAULT_WAKE_TIME)

    print(f"\n{Colors.BOLD}Recovery Strategy:{Colors.END}")
    print(f"  Daily target:      {Colors.GREEN}{hours_to_hm(daily_target)}{Colors.END} hours/night")
    print(f"  Recommended bed:   {Colors.MAGENTA}{decimal_to_time(ideal_bedtime)}{Colors.END}")
    print(f"  Extra sleep/night: +{hours_to_hm(daily_recovery)} hours")
    print(f"  Est. full recovery: {int(actual_recovery_days)} days")

    # Weekly breakdown
    print(f"\n{Colors.BOLD}Weekly Targets:{Colors.END}")
    print(f"  {Colors.DIM}{'Week':<8} {'Bedtime':>10} {'Target':>10} {'Debt Left':>12}{Colors.END}")
    print(f"  {'-'*42}")

    remaining_debt = debt
    today = datetime.now()

    for week in range(1, weeks + 1):
        week_target = daily_target
        week_recovery = min(remaining_debt, daily_recovery * 7)
        remaining_debt = max(0, remaining_debt - week_recovery)
        week_bedtime = calculate_recommended_bedtime(week_target, DEFAULT_WAKE_TIME)

        debt_color = Colors.GREEN if remaining_debt == 0 else Colors.YELLOW if remaining_debt < debt/2 else Colors.RED

        print(f"  Week {week:<3} {Colors.MAGENTA}{decimal_to_time(week_bedtime):>10}{Colors.END} {Colors.GREEN}{hours_to_hm(week_target):>10}{Colors.END} {debt_color}{hours_to_hm(remaining_debt):>12}{Colors.END}")

    # Daily view for next 2 weeks
    print(f"\n{Colors.BOLD}Next 14 Days:{Colors.END}")
    print(f"  {Colors.DIM}{'Date':<12} {'Day':<6} {'Bedtime':>10} {'Target':>8} {'Recovery':>12}{Colors.END}")
    print(f"  {'-'*52}")

    remaining = debt
    for day in range(14):
        date = today + timedelta(days=day)
        day_name = date.strftime('%a')
        date_str = date.strftime('%Y-%m-%d')

        # Weekend - suggest more sleep
        if date.weekday() >= 5:  # Saturday or Sunday
            target = min(OPTIMAL_SLEEP + 1, 9.0)
            recovery = target - TARGET_SLEEP
        else:
            target = daily_target
            recovery = daily_recovery

        remaining = max(0, remaining - recovery)
        recovered = debt - remaining
        bedtime = calculate_recommended_bedtime(target, DEFAULT_WAKE_TIME)

        weekend_mark = f"{Colors.CYAN}*{Colors.END}" if date.weekday() >= 5 else " "
        debt_color = Colors.GREEN if recovered >= debt else Colors.YELLOW

        print(f"  {date_str:<12} {day_name:<6} {Colors.MAGENTA}{decimal_to_time(bedtime):>10}{Colors.END} {Colors.GREEN}{hours_to_hm(target):>8}{Colors.END} {debt_color}{hours_to_hm(recovered):>10} done{Colors.END}{weekend_mark}")

    print(f"\n  {Colors.CYAN}* Weekend - extra recovery opportunity{Colors.END}")
    print()

def cmd_init(args):
    """Initialize with sample data."""
    import random

    # Generate sample data for the past 30 days with realistic variation
    # This creates a demonstration dataset showing various sleep patterns

    num_days = 30
    today = datetime.now()
    start_date = today - timedelta(days=num_days)

    sample_data = []

    # Seed for reproducible "random" data that demonstrates features
    random.seed(42)

    for i in range(num_days):
        date = start_date + timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')

        # Generate realistic but varied sleep patterns
        # Most nights 6.5-8 hours, occasional poor nights, occasional good nights
        roll = random.random()

        if roll < 0.15:  # 15% poor sleep nights (< 6 hours)
            hours = random.uniform(5.0, 6.0)
            bedtime = random.uniform(0.5, 2.0)  # Late bedtime (12:30am - 2:00am)
        elif roll < 0.25:  # 10% very good nights (8+ hours)
            hours = random.uniform(8.0, 8.5)
            bedtime = random.uniform(22.5, 23.0)  # Early bedtime (10:30pm - 11:00pm)
        else:  # 75% normal variation (6.5-8 hours)
            hours = random.uniform(6.5, 7.8)
            bedtime = random.uniform(23.0, 0.5)  # 11:00pm - 12:30am

        # Calculate wake time from bedtime and hours slept
        waketime = bedtime + hours
        if waketime >= 24:
            waketime -= 24

        sample_data.append((date_str, round(hours, 2), round(bedtime, 2), round(waketime, 2)))

    data = {
        "profile": {
            "age": 35,
            "target": TARGET_SLEEP,
            "wake_time": DEFAULT_WAKE_TIME,
            "notes": "Sample user data"
        },
        "entries": [
            {"date": d, "hours": h, "bedtime": b, "waketime": w}
            for d, h, b, w in sample_data
        ]
    }

    save_data(data)

    debt = calculate_debt(data['entries'])
    print(f"{Colors.GREEN}Initialized with {num_days} days of sample data{Colors.END}")
    print(f"Total sleep debt: {Colors.RED if debt > 0 else Colors.GREEN}{hours_to_hm(abs(debt))}{Colors.END} hours")
    print(f"\nRun '{Colors.CYAN}sleepbetter status{Colors.END}' to see full report")
    print(f"Run '{Colors.CYAN}sleepbetter recommend{Colors.END}' for personalized advice")
    print(f"Run '{Colors.CYAN}sleepbetter graph{Colors.END}' to generate visualizations")

def cmd_graph(args):
    """Generate graphical sleep visualizations and auto-display them."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import Rectangle
        import numpy as np
    except ImportError:
        print(f"{Colors.RED}Error: matplotlib required for graphs.{Colors.END}")
        print(f"Install with: pip install matplotlib")
        return

    data = load_data()
    entries = data.get('entries', [])

    if not entries:
        print(f"{Colors.YELLOW}No sleep data. Run 'sleepbetter init' first.{Colors.END}")
        return

    entries = sorted(entries, key=lambda x: x['date'])

    # Output directory
    output_dir = Path(__file__).parent

    # Set dark theme
    plt.style.use('dark_background')

    # =============================================
    # FIGURE 1: Daily Sleep Bar Chart with Debt Progression
    # =============================================
    fig1, (ax1, ax1b) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[2, 1])
    fig1.patch.set_facecolor('#1a1a2e')
    ax1.set_facecolor('#1a1a2e')
    ax1b.set_facecolor('#1a1a2e')

    dates = [datetime.strptime(e['date'], '%Y-%m-%d') for e in entries]
    hours = [e['hours'] for e in entries]

    # Color bars based on sleep amount
    colors = []
    for h in hours:
        if h >= 7.0:
            colors.append('#4ade80')  # Green
        elif h >= 6.0:
            colors.append('#fb923c')  # Orange
        else:
            colors.append('#ef4444')  # Red

    bars = ax1.bar(dates, hours, color=colors, width=0.7, edgecolor='white', linewidth=0.5)

    # Add value labels on bars
    for bar, h in zip(bars, hours):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{hours_to_hm(h)}', ha='center', va='bottom',
                fontsize=9, fontweight='bold', color='white')

    # Reference lines
    ax1.axhline(y=7.0, color='#60a5fa', linestyle='--', linewidth=2, label='Recommended minimum (7.0h)')
    ax1.axhline(y=6.0, color='#fbbf24', linestyle=':', linewidth=1.5, label='Short sleep threshold (6h)')

    avg_sleep = sum(hours) / len(hours)
    ax1.axhline(y=avg_sleep, color='#a855f7', linestyle='-', linewidth=2, label=f'Your average ({hours_to_hm(avg_sleep)}h)')

    # Shaded recommended zone
    ax1.axhspan(7.0, 9.0, alpha=0.1, color='#4ade80', label='Recommended range (7.0-9.0h)')

    ax1.set_ylabel('Sleep Duration (hours)', fontsize=12, color='white')
    ax1.set_title('Sleep Analysis & Tracking', fontsize=16, fontweight='bold', color='white', pad=20)

    ax1.set_ylim(0, 10)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax1.xaxis.set_major_locator(mdates.DayLocator())
    ax1.tick_params(axis='x', labelbottom=False)

    ax1.legend(loc='upper right', fontsize=9, facecolor='#1a1a2e', edgecolor='white')
    ax1.grid(axis='y', alpha=0.3, color='white')

    # Stats box
    debt = calculate_debt(entries)
    nights_below_7 = sum(1 for h in hours if h < 7)
    nights_below_6 = sum(1 for h in hours if h < 6)
    nights_below_5 = sum(1 for h in hours if h < 5)

    stats_text = f"""SLEEP STATISTICS
Average: {hours_to_hm(avg_sleep)} hrs/night
Target: 7-9 hrs (age 45-54)
Total Debt: {hours_to_hm(debt)} hrs

Nights < 7h: {nights_below_7}/{len(entries)} ({100*nights_below_7//len(entries)}%)
Nights < 6h: {nights_below_6}/{len(entries)} ({100*nights_below_6//len(entries)}%)
Nights < 5h: {nights_below_5}/{len(entries)} ({100*nights_below_5//len(entries)}%)"""

    ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='#16213e', edgecolor='white', alpha=0.9),
             color='white')

    # --- Bottom subplot: Progressive sleep debt ---
    progressive = calculate_progressive_debt(entries)
    prog_dates = [datetime.strptime(p['date'], '%Y-%m-%d') for p in progressive]
    prog_debt = [p['cumulative_debt'] for p in progressive]

    ax1b.fill_between(prog_dates, prog_debt, alpha=0.3, color='#ef4444')
    ax1b.plot(prog_dates, prog_debt, color='#ef4444', linewidth=2, marker='o', markersize=4)
    ax1b.axhline(y=0, color='#4ade80', linestyle='--', linewidth=1, alpha=0.5)

    ax1b.set_xlabel('Date', fontsize=12, color='white')
    ax1b.set_ylabel('Cumulative Debt (hrs)', fontsize=12, color='white')
    ax1b.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax1b.xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(ax1b.xaxis.get_majorticklabels(), rotation=45, ha='right')
    ax1b.grid(axis='y', alpha=0.3, color='white')

    # Annotate final debt
    ax1b.annotate(f'{hours_to_hm(prog_debt[-1])}h debt',
                  xy=(prog_dates[-1], prog_debt[-1]),
                  xytext=(10, 10), textcoords='offset points',
                  fontsize=10, color='#ef4444', fontweight='bold',
                  arrowprops=dict(arrowstyle='->', color='#ef4444'))

    plt.tight_layout()
    fig1_path = output_dir / 'sleep_daily.png'
    fig1.savefig(fig1_path, dpi=150, facecolor='#1a1a2e', edgecolor='none')
    print(f"{Colors.GREEN}Generated:{Colors.END} {fig1_path}")

    # =============================================
    # FIGURE 2: Trends View (like inspiration.png)
    # =============================================
    fig2, axes = plt.subplots(2, 1, figsize=(12, 10), height_ratios=[1, 1.5])
    fig2.patch.set_facecolor('#000000')

    # --- Top: Day-of-week breakdown + Typical nights ---
    ax_top = axes[0]
    ax_top.set_facecolor('#000000')

    # Day of week averages
    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    day_avgs = {i: [] for i in range(7)}
    for e in entries:
        dt = datetime.strptime(e['date'], '%Y-%m-%d')
        day_avgs[dt.weekday()].append(e['hours'])

    # Reorder to start with Sunday
    dow_order = [6, 0, 1, 2, 3, 4, 5]  # Sun, Mon, Tue, Wed, Thu, Fri, Sat
    dow_labels = ['All'] + day_names
    dow_values = [avg_sleep] + [sum(day_avgs[d])/len(day_avgs[d]) if day_avgs[d] else 0 for d in dow_order]

    # Create pill-shaped day indicators
    for i, (label, val) in enumerate(zip(dow_labels, dow_values)):
        color = '#3b82f6' if i == 0 else '#1f2937'
        rect = Rectangle((i * 1.2, 0), 1, 1.5, facecolor=color, edgecolor='none',
                         transform=ax_top.transData, clip_on=False)
        ax_top.add_patch(rect)
        ax_top.text(i * 1.2 + 0.5, 1.1, label, ha='center', va='center',
                   fontsize=11, fontweight='bold', color='white')
        ax_top.text(i * 1.2 + 0.5, 0.4, f'{val:.1f}h', ha='center', va='center',
                   fontsize=10, color='#9ca3af' if val < 7 else '#4ade80')

    ax_top.set_xlim(-0.5, 9)
    ax_top.set_ylim(-0.5, 6)
    ax_top.axis('off')
    ax_top.set_title('Trends', fontsize=24, fontweight='bold', color='white', loc='left', pad=20)

    # Add typical nights info
    entries_with_times = [e for e in entries if 'bedtime' in e and 'waketime' in e]
    if entries_with_times:
        avg_bed = sum(e['bedtime'] for e in entries_with_times) / len(entries_with_times)
        avg_wake = sum(e['waketime'] for e in entries_with_times) / len(entries_with_times)
        ax_top.text(0, 4.5, 'Typical Nights', fontsize=14, fontweight='bold', color='white')
        ax_top.text(0, 3.5, f'{decimal_to_time(avg_bed)} → {decimal_to_time(avg_wake)}  ({hours_to_hm(avg_sleep)})',
                   fontsize=12, color='#9ca3af')

    # --- Bottom: Nightly trends (bedtime/wake time over time) ---
    ax_bot = axes[1]
    ax_bot.set_facecolor('#000000')

    if entries_with_times:
        trend_dates = [datetime.strptime(e['date'], '%Y-%m-%d') for e in entries_with_times]
        bedtimes = [e['bedtime'] for e in entries_with_times]
        waketimes = [e['waketime'] for e in entries_with_times]

        # Adjust bedtimes > 12 to show as negative (previous day evening)
        bedtimes_adj = [b if b < 12 else b - 24 for b in bedtimes]

        # Plot wake times (blue)
        ax_bot.scatter(trend_dates, waketimes, color='#60a5fa', s=80, zorder=3, label='Wake time')
        ax_bot.plot(trend_dates, waketimes, color='#60a5fa', linewidth=2, alpha=0.7)

        # Plot bedtimes (magenta/pink)
        ax_bot.scatter(trend_dates, bedtimes_adj, color='#f472b6', s=80, zorder=3, label='Bedtime')
        ax_bot.plot(trend_dates, bedtimes_adj, color='#f472b6', linewidth=2, alpha=0.7)

        ax_bot.set_ylabel('Time of Day', fontsize=12, color='white')
        ax_bot.set_xlabel('', fontsize=12, color='white')

        # Y-axis: show times from 8pm to 12pm
        ax_bot.set_ylim(-4, 12)  # -4 = 8pm, 12 = noon
        yticks = [-4, -2, 0, 2, 4, 6, 8, 10, 12]
        ylabels = ['8p', '10p', '12a', '2a', '4a', '6a', '8a', '10a', '12p']
        ax_bot.set_yticks(yticks)
        ax_bot.set_yticklabels(ylabels, color='white')

        ax_bot.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax_bot.tick_params(colors='white')

        ax_bot.set_title(f'Nightly Trends\n{decimal_to_time(avg_wake)} to {decimal_to_time(avg_bed)} ({len(entries_with_times)} Night Avg)',
                        fontsize=14, color='white', loc='left')

        ax_bot.legend(loc='upper right', facecolor='#000000', edgecolor='white', labelcolor='white')
        ax_bot.grid(axis='y', alpha=0.2, color='white')

        # Add horizontal bands for sleep period
        ax_bot.axhspan(-4, 0, alpha=0.05, color='#f472b6')  # Evening zone
        ax_bot.axhspan(6, 8, alpha=0.05, color='#60a5fa')   # Morning zone

        # Add recommended bedtime line
        rec_bedtime = calculate_recommended_bedtime(TARGET_SLEEP, DEFAULT_WAKE_TIME)
        rec_bedtime_adj = rec_bedtime if rec_bedtime < 12 else rec_bedtime - 24
        ax_bot.axhline(y=rec_bedtime_adj, color='#4ade80', linestyle='--', linewidth=1, alpha=0.7)
        ax_bot.text(trend_dates[-1], rec_bedtime_adj + 0.3, f'Ideal: {decimal_to_time(rec_bedtime)}',
                   color='#4ade80', fontsize=9, ha='right')
    else:
        ax_bot.text(0.5, 0.5, 'No bedtime/wake time data available\nUse "sleepbetter add" to add entries with times',
                   ha='center', va='center', fontsize=14, color='#9ca3af', transform=ax_bot.transAxes)
        ax_bot.axis('off')

    plt.tight_layout()
    fig2_path = output_dir / 'sleep_trends.png'
    fig2.savefig(fig2_path, dpi=150, facecolor='#000000', edgecolor='none')
    print(f"{Colors.GREEN}Generated:{Colors.END} {fig2_path}")

    plt.close('all')

    print(f"\n{Colors.CYAN}Opening visualizations...{Colors.END}")

    # Auto-open the images in separate windows
    open_image(fig1_path)
    open_image(fig2_path)

    print(f"  1. {fig1_path.name} - Daily sleep + debt progression")
    print(f"  2. {fig2_path.name} - Sleep timing trends")

def cmd_calendar(args):
    """Show calendar view of sleep patterns."""
    data = load_data()
    entries = data.get('entries', [])

    if not entries:
        print(f"{Colors.YELLOW}No sleep data. Run 'sleepbetter init' first.{Colors.END}")
        return

    # Create lookup by date
    sleep_by_date = {e['date']: e['hours'] for e in entries}

    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  SLEEP CALENDAR{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

    # Legend
    print(f"  {Colors.GREEN}\u2588{Colors.END} 7+ hrs  {Colors.YELLOW}\u2588{Colors.END} 6-7 hrs  {Colors.RED}\u2588{Colors.END} <6 hrs  {Colors.DIM}\u2591{Colors.END} no data\n")

    # Find date range
    dates = sorted(sleep_by_date.keys())
    start = datetime.strptime(dates[0], '%Y-%m-%d')
    end = datetime.strptime(dates[-1], '%Y-%m-%d')

    # Extend to show future weeks
    weeks_ahead = args.weeks or 3
    end = max(end, datetime.now() + timedelta(days=weeks_ahead*7))

    # Print header
    print(f"  {Colors.DIM}{'Mon':>5} {'Tue':>5} {'Wed':>5} {'Thu':>5} {'Fri':>5} {'Sat':>5} {'Sun':>5}{Colors.END}")

    # Start from beginning of that week
    current = start - timedelta(days=start.weekday())

    while current <= end:
        week_str = f"  "
        for day in range(7):
            date = current + timedelta(days=day)
            date_str = date.strftime('%Y-%m-%d')

            if date_str in sleep_by_date:
                hours = sleep_by_date[date_str]
                color = get_color_for_sleep(hours)
                block = f"{color}{hours_to_hm(hours):>5}{Colors.END}"
            elif date <= datetime.now():
                block = f"{Colors.DIM}{'--':>5}{Colors.END}"
            else:
                block = f"{Colors.DIM}{'(7+)':>5}{Colors.END}"

            week_str += block + " "

        week_label = current.strftime('%b %d')
        print(f"{Colors.DIM}{week_label:<6}{Colors.END}{week_str}")
        current += timedelta(days=7)

    print()

def cmd_history():
    """View sleep history for different time ranges."""
    data = load_data()
    entries = data.get('entries', [])

    if not entries:
        print(f"{Colors.YELLOW}No sleep data available.{Colors.END}")
        return

    entries = sorted(entries, key=lambda x: x['date'])

    print(f"\n{Colors.BOLD}{Colors.CYAN}View Sleep History{Colors.END}")
    print(f"{Colors.DIM}Select a time range to analyze:{Colors.END}\n")

    ranges = [
        ('1', 15, '15 days'),
        ('2', 30, '30 days'),
        ('3', 45, '45 days'),
        ('4', 90, '90 days (3 months)'),
        ('5', 120, '120 days (4 months)'),
        ('6', 365, '365 days (1 year)'),
        ('7', None, 'All data'),
    ]

    for key, days, label in ranges:
        print(f"  {Colors.CYAN}{key}{Colors.END}  {label}")

    print(f"  {Colors.DIM}b  Back to main menu{Colors.END}")

    choice = input(f"\n{Colors.BOLD}Select range:{Colors.END} ").strip().lower()

    if choice == 'b':
        return

    # Find the selected range
    selected = None
    for key, days, label in ranges:
        if choice == key:
            selected = (days, label)
            break

    if not selected:
        print(f"{Colors.YELLOW}Invalid selection.{Colors.END}")
        return

    days_back, label = selected
    today = datetime.now()

    # Filter entries by date range
    if days_back is not None:
        cutoff = today - timedelta(days=days_back)
        filtered = [e for e in entries if datetime.strptime(e['date'], '%Y-%m-%d') >= cutoff]
    else:
        filtered = entries

    if not filtered:
        print(f"\n{Colors.YELLOW}No data available for the last {label}.{Colors.END}")
        return

    # Calculate statistics for this range
    total_hours = sum(e['hours'] for e in filtered)
    avg_sleep = total_hours / len(filtered)
    debt = calculate_debt(filtered)

    nights_below_7 = sum(1 for e in filtered if e['hours'] < 7)
    nights_below_6 = sum(1 for e in filtered if e['hours'] < 6)
    nights_below_5 = sum(1 for e in filtered if e['hours'] < 5)

    best_night = max(filtered, key=lambda x: x['hours'])
    worst_night = min(filtered, key=lambda x: x['hours'])

    # Day of week analysis
    dow_totals = {i: [] for i in range(7)}
    for e in filtered:
        dt = datetime.strptime(e['date'], '%Y-%m-%d')
        dow_totals[dt.weekday()].append(e['hours'])

    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  SLEEP ANALYSIS: {label.upper()}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

    print(f"{Colors.BOLD}Summary ({len(filtered)} nights):{Colors.END}")
    print(f"  Average sleep:     {get_color_for_sleep(avg_sleep)}{hours_to_hm(avg_sleep)}{Colors.END} hrs/night")
    print(f"  Total sleep debt:  {Colors.RED if debt > 0 else Colors.GREEN}{hours_to_hm(abs(debt))}{Colors.END} hours")
    print(f"  Target:            {hours_to_hm(TARGET_SLEEP)} hrs/night")

    print(f"\n{Colors.BOLD}Sleep Quality Breakdown:{Colors.END}")
    pct_below_7 = 100 * nights_below_7 // len(filtered) if filtered else 0
    pct_below_6 = 100 * nights_below_6 // len(filtered) if filtered else 0
    pct_below_5 = 100 * nights_below_5 // len(filtered) if filtered else 0

    print(f"  {Colors.GREEN}Good (7+ hrs):{Colors.END}    {len(filtered) - nights_below_7} nights ({100 - pct_below_7}%)")
    print(f"  {Colors.YELLOW}Short (6-7 hrs):{Colors.END}  {nights_below_6 - nights_below_5 if nights_below_6 > nights_below_5 else nights_below_7 - nights_below_6} nights")
    print(f"  {Colors.RED}Severe (<6 hrs):{Colors.END}  {nights_below_6} nights ({pct_below_6}%)")

    print(f"\n{Colors.BOLD}Extremes:{Colors.END}")
    print(f"  Best night:  {Colors.GREEN}{best_night['date']} - {hours_to_hm(best_night['hours'])} hrs{Colors.END}")
    print(f"  Worst night: {Colors.RED}{worst_night['date']} - {hours_to_hm(worst_night['hours'])} hrs{Colors.END}")

    # Day of week breakdown
    print(f"\n{Colors.BOLD}Day of Week Averages:{Colors.END}")
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for i, name in enumerate(day_names):
        if dow_totals[i]:
            avg = sum(dow_totals[i]) / len(dow_totals[i])
            color = get_color_for_sleep(avg)
            bar_len = int(avg * 3)  # Simple bar visualization
            bar = '█' * bar_len
            print(f"  {name}: {color}{hours_to_hm(avg):>5}{Colors.END}  {color}{bar}{Colors.END}")
        else:
            print(f"  {name}: {Colors.DIM}no data{Colors.END}")

    # Trend analysis (if enough data)
    if len(filtered) >= 14:
        first_week = filtered[:7]
        last_week = filtered[-7:]
        first_avg = sum(e['hours'] for e in first_week) / 7
        last_avg = sum(e['hours'] for e in last_week) / 7
        change = last_avg - first_avg

        print(f"\n{Colors.BOLD}Trend Analysis:{Colors.END}")
        print(f"  First 7 nights avg: {get_color_for_sleep(first_avg)}{hours_to_hm(first_avg)}{Colors.END}")
        print(f"  Last 7 nights avg:  {get_color_for_sleep(last_avg)}{hours_to_hm(last_avg)}{Colors.END}")

        if change > 0.25:
            print(f"  Trend: {Colors.GREEN}↑ Improving (+{hours_to_hm(change)}){Colors.END}")
        elif change < -0.25:
            print(f"  Trend: {Colors.RED}↓ Declining ({hours_to_hm(change)}){Colors.END}")
        else:
            print(f"  Trend: {Colors.YELLOW}→ Stable{Colors.END}")

    # Progressive debt over this period
    if len(filtered) > 1:
        print(f"\n{Colors.BOLD}Debt Progression:{Colors.END}")
        progressive = calculate_progressive_debt(filtered)

        # Show start, middle, and end points
        points = [0, len(progressive)//2, -1]
        for idx in points:
            p = progressive[idx]
            debt_color = Colors.GREEN if p['cumulative_debt'] <= 0 else Colors.YELLOW if p['cumulative_debt'] < 7 else Colors.RED
            print(f"  {p['date']}: {debt_color}{hours_to_hm(p['cumulative_debt'])} debt{Colors.END}")

    print()


def cmd_catchup():
    """Prompt user to fill in missing days."""
    data = load_data()
    entries = data.get('entries', [])
    missing = get_missing_days(entries)

    if not missing:
        print(f"\n{Colors.GREEN}All caught up! No missing days.{Colors.END}")
        return False  # No changes made

    print(f"\n{Colors.BOLD}{Colors.YELLOW}Missing Sleep Data{Colors.END}")
    print(f"{Colors.DIM}You have {len(missing)} day(s) without sleep records.{Colors.END}")
    print(f"{Colors.DIM}Enter sleep duration for each, or press Enter to skip.{Colors.END}\n")

    changes_made = False
    wake_time = data.get('profile', {}).get('wake_time', DEFAULT_WAKE_TIME)

    for date_str in missing:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        day_name = dt.strftime('%A, %b %d')

        hours_input = input(f"  {Colors.CYAN}{day_name}{Colors.END} - Hours slept (h:mm): ").strip()

        if not hours_input:
            print(f"    {Colors.DIM}Skipped{Colors.END}")
            continue

        try:
            hours = hm_to_hours(hours_input)
        except:
            print(f"    {Colors.RED}Invalid format, skipped{Colors.END}")
            continue

        # Calculate bedtime
        bedtime = wake_time - hours
        if bedtime < 0:
            bedtime += 24

        entry = {
            'date': date_str,
            'hours': hours,
            'bedtime': bedtime,
            'waketime': wake_time
        }

        entries.append(entry)
        changes_made = True

        color = get_color_for_sleep(hours)
        deficit = TARGET_SLEEP - hours
        deficit_str = f"+{hours_to_hm(abs(deficit))}" if deficit <= 0 else f"-{hours_to_hm(deficit)}"
        deficit_color = Colors.GREEN if deficit <= 0 else Colors.RED

        print(f"    {Colors.GREEN}Added:{Colors.END} {color}{hours_to_hm(hours)}{Colors.END} hrs ({deficit_color}{deficit_str}{Colors.END})")

    if changes_made:
        data['entries'] = sorted(entries, key=lambda x: x['date'])
        save_data(data)
        debt = calculate_debt(data['entries'])
        print(f"\n{Colors.GREEN}Data saved.{Colors.END} Total sleep debt: {Colors.RED if debt > 0 else Colors.GREEN}{hours_to_hm(abs(debt))}{Colors.END} hours")

    return changes_made


def cmd_interactive_log():
    """Interactive log entry from menu."""
    data = load_data()

    print(f"\n{Colors.BOLD}{Colors.CYAN}Log Sleep Entry{Colors.END}\n")

    # Date
    date_input = input("Date (YYYY-MM-DD, MM-DD, today, yesterday) [today]: ").strip()
    if not date_input or date_input.lower() == 'today':
        date = datetime.now().strftime('%Y-%m-%d')
    elif date_input.lower() == 'yesterday':
        date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    elif len(date_input) == 5 and '-' in date_input:  # MM-DD format
        date = f"2025-{date_input}"
    else:
        date = date_input

    # Hours
    hours_input = input("Hours slept (h:mm, e.g., 7:30): ").strip()
    if not hours_input:
        print(f"{Colors.YELLOW}Cancelled.{Colors.END}")
        return

    hours = hm_to_hours(hours_input)

    # Calculate bedtime from wake time
    wake_time = data.get('profile', {}).get('wake_time', DEFAULT_WAKE_TIME)
    bedtime = wake_time - hours
    if bedtime < 0:
        bedtime += 24

    # Build and save entry
    entry = {
        'date': date,
        'hours': hours,
        'bedtime': bedtime,
        'waketime': wake_time
    }

    entries = data.get('entries', [])
    existing = next((i for i, e in enumerate(entries) if e['date'] == date), None)

    if existing is not None:
        entries[existing] = entry
        action = "Updated"
    else:
        entries.append(entry)
        action = "Added"

    data['entries'] = sorted(entries, key=lambda x: x['date'])
    save_data(data)

    # Calculate debt
    debt = calculate_debt(data['entries'])

    color = get_color_for_sleep(hours)
    deficit = TARGET_SLEEP - hours

    print(f"\n{Colors.GREEN}{action}:{Colors.END} {date} - {color}{hours_to_hm(hours)}{Colors.END} hours")
    print(f"  Est. bedtime: {Colors.MAGENTA}{decimal_to_time(bedtime)}{Colors.END} → wake {Colors.BLUE}{decimal_to_time(wake_time)}{Colors.END}")

    if deficit > 0:
        print(f"  Daily deficit: {Colors.RED}-{hours_to_hm(deficit)}{Colors.END}")
    else:
        print(f"  Daily surplus: {Colors.GREEN}+{hours_to_hm(abs(deficit))}{Colors.END}")

    print(f"  Total sleep debt: {Colors.RED if debt > 0 else Colors.GREEN}{hours_to_hm(abs(debt))}{Colors.END} hours")


def generate_graphs_silent():
    """Generate graphs without printing, return paths."""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import Rectangle
        import numpy as np
    except ImportError:
        return None, None

    data = load_data()
    entries = data.get('entries', [])

    if not entries:
        return None, None

    entries = sorted(entries, key=lambda x: x['date'])
    output_dir = Path(__file__).parent

    plt.style.use('dark_background')

    # FIGURE 1: Daily Sleep + Debt Progression
    fig1, (ax1, ax1b) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[2, 1])
    fig1.patch.set_facecolor('#1a1a2e')
    ax1.set_facecolor('#1a1a2e')
    ax1b.set_facecolor('#1a1a2e')

    dates = [datetime.strptime(e['date'], '%Y-%m-%d') for e in entries]
    hours = [e['hours'] for e in entries]

    colors = []
    for h in hours:
        if h >= 7.0:
            colors.append('#4ade80')
        elif h >= 6.0:
            colors.append('#fb923c')
        else:
            colors.append('#ef4444')

    bars = ax1.bar(dates, hours, color=colors, width=0.7, edgecolor='white', linewidth=0.5)

    for bar, h in zip(bars, hours):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{hours_to_hm(h)}', ha='center', va='bottom',
                fontsize=9, fontweight='bold', color='white')

    # Add "today" as a crosshatch bar showing target (pending sleep)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = today.strftime('%Y-%m-%d')

    # Only show today bar if today isn't already in the data
    if today_str not in [e['date'] for e in entries]:
        debt = calculate_debt(entries)
        extra_needed = min(debt / 7, 1.5) if debt > 0 else 0
        target_tonight = TARGET_SLEEP + extra_needed

        # Add crosshatch bar for today (pending)
        ax1.bar([today], [target_tonight], width=0.7,
                color='none', edgecolor='#60a5fa', linewidth=2,
                hatch='///', alpha=0.8)

        # Label for today
        ax1.text(today, target_tonight + 0.1, f'Tonight\n{hours_to_hm(target_tonight)}?',
                ha='center', va='bottom', fontsize=8, color='#60a5fa', style='italic')

    ax1.axhline(y=7.0, color='#60a5fa', linestyle='--', linewidth=2, label='Recommended minimum (7.0h)')
    ax1.axhline(y=6.0, color='#fbbf24', linestyle=':', linewidth=1.5, label='Short sleep threshold (6h)')

    avg_sleep = sum(hours) / len(hours)
    ax1.axhline(y=avg_sleep, color='#a855f7', linestyle='-', linewidth=2, label=f'Your average ({hours_to_hm(avg_sleep)}h)')
    ax1.axhspan(7.0, 9.0, alpha=0.1, color='#4ade80', label='Recommended range (7.0-9.0h)')

    ax1.set_ylabel('Sleep Duration (hours)', fontsize=12, color='white')
    ax1.set_title('Sleep Analysis & Tracking', fontsize=16, fontweight='bold', color='white', pad=20)
    ax1.set_ylim(0, 10)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax1.xaxis.set_major_locator(mdates.DayLocator())
    ax1.tick_params(axis='x', labelbottom=False)
    ax1.legend(loc='upper right', fontsize=9, facecolor='#1a1a2e', edgecolor='white')
    ax1.grid(axis='y', alpha=0.3, color='white')

    debt = calculate_debt(entries)
    nights_below_7 = sum(1 for h in hours if h < 7)
    nights_below_6 = sum(1 for h in hours if h < 6)
    nights_below_5 = sum(1 for h in hours if h < 5)

    stats_text = f"""SLEEP STATISTICS
Average: {hours_to_hm(avg_sleep)} hrs/night
Target: 7-9 hrs (age 45-54)
Total Debt: {hours_to_hm(debt)} hrs

Nights < 7h: {nights_below_7}/{len(entries)} ({100*nights_below_7//len(entries)}%)
Nights < 6h: {nights_below_6}/{len(entries)} ({100*nights_below_6//len(entries)}%)
Nights < 5h: {nights_below_5}/{len(entries)} ({100*nights_below_5//len(entries)}%)"""

    ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='#16213e', edgecolor='white', alpha=0.9),
             color='white')

    progressive = calculate_progressive_debt(entries)
    prog_dates = [datetime.strptime(p['date'], '%Y-%m-%d') for p in progressive]
    prog_debt = [p['cumulative_debt'] for p in progressive]

    ax1b.fill_between(prog_dates, prog_debt, alpha=0.3, color='#ef4444')
    ax1b.plot(prog_dates, prog_debt, color='#ef4444', linewidth=2, marker='o', markersize=4)
    ax1b.axhline(y=0, color='#4ade80', linestyle='--', linewidth=1, alpha=0.5)

    ax1b.set_xlabel('Date', fontsize=12, color='white')
    ax1b.set_ylabel('Cumulative Debt (hrs)', fontsize=12, color='white')
    ax1b.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax1b.xaxis.set_major_locator(mdates.DayLocator())
    plt.setp(ax1b.xaxis.get_majorticklabels(), rotation=45, ha='right')
    ax1b.grid(axis='y', alpha=0.3, color='white')

    ax1b.annotate(f'{hours_to_hm(prog_debt[-1])}h debt',
                  xy=(prog_dates[-1], prog_debt[-1]),
                  xytext=(10, 10), textcoords='offset points',
                  fontsize=10, color='#ef4444', fontweight='bold',
                  arrowprops=dict(arrowstyle='->', color='#ef4444'))

    plt.tight_layout()
    fig1_path = output_dir / 'sleep_daily.png'
    fig1.savefig(fig1_path, dpi=150, facecolor='#1a1a2e', edgecolor='none')

    # FIGURE 2: Trends View
    fig2, axes = plt.subplots(2, 1, figsize=(12, 10), height_ratios=[1, 1.5])
    fig2.patch.set_facecolor('#000000')

    ax_top = axes[0]
    ax_top.set_facecolor('#000000')

    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    day_avgs = {i: [] for i in range(7)}
    for e in entries:
        dt = datetime.strptime(e['date'], '%Y-%m-%d')
        day_avgs[dt.weekday()].append(e['hours'])

    dow_order = [6, 0, 1, 2, 3, 4, 5]
    dow_labels = ['All'] + day_names
    dow_values = [avg_sleep] + [sum(day_avgs[d])/len(day_avgs[d]) if day_avgs[d] else 0 for d in dow_order]

    for i, (label, val) in enumerate(zip(dow_labels, dow_values)):
        color = '#3b82f6' if i == 0 else '#1f2937'
        rect = Rectangle((i * 1.2, 0), 1, 1.5, facecolor=color, edgecolor='none',
                         transform=ax_top.transData, clip_on=False)
        ax_top.add_patch(rect)
        ax_top.text(i * 1.2 + 0.5, 1.1, label, ha='center', va='center',
                   fontsize=11, fontweight='bold', color='white')
        ax_top.text(i * 1.2 + 0.5, 0.4, f'{val:.1f}h', ha='center', va='center',
                   fontsize=10, color='#9ca3af' if val < 7 else '#4ade80')

    ax_top.set_xlim(-0.5, 9)
    ax_top.set_ylim(-0.5, 6)
    ax_top.axis('off')
    ax_top.set_title('Trends', fontsize=24, fontweight='bold', color='white', loc='left', pad=20)

    entries_with_times = [e for e in entries if 'bedtime' in e and 'waketime' in e]
    if entries_with_times:
        avg_bed = sum(e['bedtime'] for e in entries_with_times) / len(entries_with_times)
        avg_wake = sum(e['waketime'] for e in entries_with_times) / len(entries_with_times)
        ax_top.text(0, 4.5, 'Typical Nights', fontsize=14, fontweight='bold', color='white')
        ax_top.text(0, 3.5, f'{decimal_to_time(avg_bed)} → {decimal_to_time(avg_wake)}  ({hours_to_hm(avg_sleep)})',
                   fontsize=12, color='#9ca3af')

    ax_bot = axes[1]
    ax_bot.set_facecolor('#000000')

    if entries_with_times:
        trend_dates = [datetime.strptime(e['date'], '%Y-%m-%d') for e in entries_with_times]
        bedtimes = [e['bedtime'] for e in entries_with_times]
        waketimes = [e['waketime'] for e in entries_with_times]

        bedtimes_adj = [b if b < 12 else b - 24 for b in bedtimes]

        ax_bot.scatter(trend_dates, waketimes, color='#60a5fa', s=80, zorder=3, label='Wake time')
        ax_bot.plot(trend_dates, waketimes, color='#60a5fa', linewidth=2, alpha=0.7)

        ax_bot.scatter(trend_dates, bedtimes_adj, color='#f472b6', s=80, zorder=3, label='Bedtime')
        ax_bot.plot(trend_dates, bedtimes_adj, color='#f472b6', linewidth=2, alpha=0.7)

        ax_bot.set_ylabel('Time of Day', fontsize=12, color='white')
        ax_bot.set_ylim(-4, 12)
        yticks = [-4, -2, 0, 2, 4, 6, 8, 10, 12]
        ylabels = ['8p', '10p', '12a', '2a', '4a', '6a', '8a', '10a', '12p']
        ax_bot.set_yticks(yticks)
        ax_bot.set_yticklabels(ylabels, color='white')

        ax_bot.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax_bot.tick_params(colors='white')

        ax_bot.set_title(f'Nightly Trends\n{decimal_to_time(avg_wake)} to {decimal_to_time(avg_bed)} ({len(entries_with_times)} Night Avg)',
                        fontsize=14, color='white', loc='left')

        ax_bot.legend(loc='upper right', facecolor='#000000', edgecolor='white', labelcolor='white')
        ax_bot.grid(axis='y', alpha=0.2, color='white')

        ax_bot.axhspan(-4, 0, alpha=0.05, color='#f472b6')
        ax_bot.axhspan(6, 8, alpha=0.05, color='#60a5fa')

        rec_bedtime = calculate_recommended_bedtime(TARGET_SLEEP, DEFAULT_WAKE_TIME)
        rec_bedtime_adj = rec_bedtime if rec_bedtime < 12 else rec_bedtime - 24
        ax_bot.axhline(y=rec_bedtime_adj, color='#4ade80', linestyle='--', linewidth=1, alpha=0.7)
        ax_bot.text(trend_dates[-1], rec_bedtime_adj + 0.3, f'Ideal: {decimal_to_time(rec_bedtime)}',
                   color='#4ade80', fontsize=9, ha='right')

    plt.tight_layout()
    fig2_path = output_dir / 'sleep_trends.png'
    fig2.savefig(fig2_path, dpi=150, facecolor='#000000', edgecolor='none')

    plt.close('all')

    return fig1_path, fig2_path


def interactive_mode():
    """Main interactive mode - displays graphs, status, and menu."""
    data = load_data()
    entries = data.get('entries', [])

    if not entries:
        print(f"{Colors.YELLOW}No sleep data found. Initializing with December 2025 data...{Colors.END}")
        cmd_init(None)
        data = load_data()
        entries = data.get('entries', [])

    # Check for missing days on startup
    missing = get_missing_days(entries)
    if missing:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}You have {len(missing)} day(s) with missing sleep data.{Colors.END}")
        catch_up = input(f"Would you like to fill them in now? [Y/n]: ").strip().lower()
        if catch_up != 'n':
            if cmd_catchup():
                data = load_data()  # Reload after catching up
                entries = data.get('entries', [])

    # Generate and display graphs
    print(f"\n{Colors.CYAN}Generating visualizations...{Colors.END}")
    fig1_path, fig2_path = generate_graphs_silent()

    if fig1_path and fig2_path:
        open_image(fig1_path)
        open_image(fig2_path)
        print(f"{Colors.GREEN}Charts opened in separate windows.{Colors.END}\n")
    else:
        print(f"{Colors.YELLOW}Could not generate graphs (matplotlib may not be installed).{Colors.END}\n")

    # Main loop
    while True:
        # Reload data each iteration
        data = load_data()
        entries = sorted(data.get('entries', []), key=lambda x: x['date'])
        missing = get_missing_days(entries)

        total_hours = sum(e['hours'] for e in entries)
        avg_sleep = total_hours / len(entries)
        debt = calculate_debt(entries)

        recent = entries[-7:] if len(entries) >= 7 else entries
        recent_avg = sum(e['hours'] for e in recent) / len(recent)

        print(f"{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}  SLEEPBETTER - Sleep Debt Tracker{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

        print(f"  {Colors.BOLD}Total nights tracked:{Colors.END} {len(entries)}")
        print(f"  {Colors.BOLD}Average sleep:{Colors.END}        {get_color_for_sleep(avg_sleep)}{hours_to_hm(avg_sleep)}{Colors.END} hrs/night")
        print(f"  {Colors.BOLD}Last 7 nights avg:{Colors.END}    {get_color_for_sleep(recent_avg)}{hours_to_hm(recent_avg)}{Colors.END} hrs/night")
        print(f"  {Colors.BOLD}Total sleep debt:{Colors.END}     {Colors.RED if debt > 0 else Colors.GREEN}{hours_to_hm(abs(debt))}{Colors.END} hours")

        # Tonight's recommendation summary
        if debt > 0:
            extra_needed = min(debt / 7, 1.5)
            target_tonight = TARGET_SLEEP + extra_needed
            ideal_bedtime = calculate_recommended_bedtime(target_tonight, DEFAULT_WAKE_TIME)
            print(f"\n  {Colors.BOLD}Tonight:{Colors.END} Sleep {Colors.GREEN}{hours_to_hm(target_tonight)}{Colors.END} hrs → Bed by {Colors.MAGENTA}{decimal_to_time(ideal_bedtime)}{Colors.END}")

        # Last entry
        if entries:
            last = entries[-1]
            print(f"\n  {Colors.DIM}Last entry: {last['date']} - {hours_to_hm(last['hours'])} hrs{Colors.END}")

        # Menu
        print(f"\n{Colors.BOLD}{'─'*60}{Colors.END}")

        # Show option 0 with missing count if applicable
        if missing:
            print(f"  {Colors.YELLOW}0{Colors.END}  Catch up on missing days ({Colors.YELLOW}{len(missing)} day{'s' if len(missing) > 1 else ''}{Colors.END})")
        else:
            print(f"  {Colors.DIM}0  Catch up on missing days (none){Colors.END}")

        print(f"  {Colors.CYAN}1{Colors.END}  Log sleep")
        print(f"  {Colors.CYAN}2{Colors.END}  View recommendations")
        print(f"  {Colors.CYAN}3{Colors.END}  View recovery plan")
        print(f"  {Colors.CYAN}4{Colors.END}  Refresh graphs")
        print(f"  {Colors.CYAN}5{Colors.END}  View full status")
        print(f"  {Colors.CYAN}6{Colors.END}  View history (15/30/90/365 days)")
        print(f"  {Colors.CYAN}q{Colors.END}  Quit")
        print(f"{Colors.BOLD}{'─'*60}{Colors.END}")

        choice = input(f"\n{Colors.BOLD}Choose option:{Colors.END} ").strip().lower()

        if choice == '0':
            if cmd_catchup():
                # Regenerate graphs if data changed
                print(f"\n{Colors.CYAN}Regenerating visualizations...{Colors.END}")
                fig1_path, fig2_path = generate_graphs_silent()
                if fig1_path and fig2_path:
                    open_image(fig1_path)
                    open_image(fig2_path)
                    print(f"{Colors.GREEN}Charts refreshed.{Colors.END}")
        elif choice == '1':
            cmd_interactive_log()
        elif choice == '2':
            cmd_recommend(None)
        elif choice == '3':
            class PlanArgs:
                weeks = 3
            cmd_plan(PlanArgs())
        elif choice == '4':
            print(f"\n{Colors.CYAN}Regenerating visualizations...{Colors.END}")
            fig1_path, fig2_path = generate_graphs_silent()
            if fig1_path and fig2_path:
                open_image(fig1_path)
                open_image(fig2_path)
                print(f"{Colors.GREEN}Charts refreshed and opened.{Colors.END}")
        elif choice == '5':
            cmd_status(None)
        elif choice == '6':
            cmd_history()
        elif choice == 'q' or choice == 'quit' or choice == 'exit':
            print(f"\n{Colors.GREEN}Sleep well! Aim for bed by 22:30 tonight.{Colors.END}\n")
            break
        else:
            print(f"{Colors.YELLOW}Invalid option. Please enter 0-6 or q.{Colors.END}")

        input(f"\n{Colors.DIM}Press Enter to continue...{Colors.END}")
        print("\n" * 2)


def main():
    parser = argparse.ArgumentParser(
        description='SleepBetter - Track sleep debt and plan recovery',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Run without arguments for interactive mode with visualizations.

Direct commands:
  sleepbetter init                    Initialize with December data
  sleepbetter status                  Show current sleep status
  sleepbetter log 12-16 7:30          Log 7h30m for Dec 16
  sleepbetter log today 6:45          Log 6h45m for today
  sleepbetter recommend               Get personalized advice
  sleepbetter plan                    Show recovery plan
  sleepbetter graph                   Generate & display charts
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize with December 2025 data')
    init_parser.set_defaults(func=cmd_init)

    # Status command
    status_parser = subparsers.add_parser('status', help='Show sleep status and debt')
    status_parser.set_defaults(func=cmd_status)

    # Log command (simple: log <date> <hours>)
    log_parser = subparsers.add_parser('log', help='Log sleep: log <date> <hours:min>')
    log_parser.add_argument('date', help='Date: YYYY-MM-DD, MM-DD, today, or yesterday')
    log_parser.add_argument('hours', help='Hours slept (h:mm format, e.g., 7:30)')
    log_parser.set_defaults(func=cmd_log)

    # Add command (detailed)
    add_parser = subparsers.add_parser('add', help='Add entry with full details')
    add_parser.add_argument('hours', nargs='?', help='Hours slept (e.g., 7:30 or 7.5)')
    add_parser.add_argument('-d', '--date', help='Date (YYYY-MM-DD)')
    add_parser.add_argument('-b', '--bedtime', help='Bedtime (HH:MM)')
    add_parser.add_argument('-w', '--waketime', help='Wake time (HH:MM)')
    add_parser.set_defaults(func=cmd_add)

    # Recommend command
    rec_parser = subparsers.add_parser('recommend', help='Get personalized recommendations')
    rec_parser.set_defaults(func=cmd_recommend)

    # Plan command
    plan_parser = subparsers.add_parser('plan', help='Show recovery plan')
    plan_parser.add_argument('-w', '--weeks', type=int, default=3, help='Weeks to plan')
    plan_parser.set_defaults(func=cmd_plan)

    # Graph command
    graph_parser = subparsers.add_parser('graph', help='Generate visual charts')
    graph_parser.set_defaults(func=cmd_graph)

    # Calendar command
    cal_parser = subparsers.add_parser('calendar', help='Show calendar view')
    cal_parser.add_argument('-w', '--weeks', type=int, default=3, help='Weeks ahead')
    cal_parser.set_defaults(func=cmd_calendar)

    args = parser.parse_args()

    # If no command given, launch interactive mode
    if args.command is None:
        interactive_mode()
    else:
        args.func(args)

if __name__ == '__main__':
    main()
