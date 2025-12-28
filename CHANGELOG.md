# Changelog

All notable changes to SleepBetter CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-12-28

### Added

#### Wake Time Customization
- **Editable wake time**: Configure your daily wake time via menu option 7 (Edit Profile)
- **Dynamic recommendations**: All bedtime recommendations now use your configured wake time
- **Recovery plan integration**: Recovery schedules adapt to your personal wake time

### Changed
- Menu option 7 now shows "Edit profile (name, birthdate, wake time)"
- `get_sleep_recommendations()` now accepts wake_time parameter
- All hardcoded "6:45am" references replaced with dynamic wake time display
- Recommendations, recovery plans, and dashboard all use profile's wake time

### Technical
- Added wake time editing to `cmd_edit_profile()` with HH:MM input validation
- Wake time validated to reasonable range (4:00 AM - 10:00 AM)
- Updated `cmd_recommend()`, `cmd_plan()`, and interactive mode to use profile's wake_time

---

## [1.1.0] - 2025-12-24

### Added

#### Profile & Personalization
- **Profile customization**: Edit name and birthdate via menu option 7
- **Automatic age calculation**: Age computed from birthdate (handles birthdays correctly)
- **Age-based recommendations**: Dynamic sleep targets based on user's age group
- **Personalized graph titles**: Shows user's name and age group in visualizations

#### Enhanced History & Graphs
- **7-day history option**: New "7 days (1 week)" option in history view (now 8 options total)
- **Time-range graph filtering**: Select time range when refreshing graphs (7/15/30/45/90/120/365/All)
- **Dynamic date headers**: Graph titles adapt to data range (same month, multi-month, cross-year)

#### Display Improvements
- **Improved time formatting**: Stats boxes now show "6H 30M" format instead of "6:30 hrs"
- **Year boundary compatibility**: Date headers work seamlessly across 2025, 2026, and beyond

### Changed
- Menu now has 8 options (0-7) instead of 7 (0-6)
- Graph generation prompts for time range instead of using all data
- Stats box uses `hours_to_hm_labeled()` for clearer formatting

### Technical
- Added `calculate_age()` function for birthdate-based age calculation
- Added `get_age_group()` for age group descriptions
- Added `get_sleep_recommendation()` for age-appropriate targets
- Added `hours_to_hm_labeled()` for "XH YM" formatting
- Added `cmd_edit_profile()` for profile editing
- Single-file architecture now ~1,950 lines

---

## [1.0.0] - 2025-12-18

### Added

#### Core Features
- Initial release of SleepBetter CLI sleep tracking tool
- JSON-based data storage for sleep entries and user profile
- Command-line interface with argparse for all operations
- Interactive mode with menu-driven interface
- ANSI color-coded terminal output (green/yellow/red for sleep quality)

#### Tracking & Logging
- Simple sleep logging: `log <date> <hours:minutes>`
- Detailed entry mode with bedtime/wake time input
- Support for flexible date formats (YYYY-MM-DD, MM-DD, today, yesterday)
- Automatic bedtime calculation from wake time and duration
- Missing days detection and catch-up prompts

#### Calculations & Analytics
- Cumulative sleep debt tracking
- Progressive debt calculation showing debt over time
- Recommended bedtime calculator with sleep onset latency buffer
- Day-of-week sleep pattern analysis
- Historical analysis over multiple time ranges (15/30/45/90/120/365 days)

#### Visualizations
- Dark-themed matplotlib visualizations with two chart types:
  - **Sleep Daily**: Bar chart with color-coded sleep duration + debt progression
  - **Sleep Trends**: Day-of-week breakdown and bedtime/wake time trends
- Auto-display of generated PNG charts (cross-platform)
- Crosshatch pattern for "tonight's target" (pending sleep)
- Stats box overlay with summary statistics
- Recommended sleep zone shading (7-9 hours)

#### Recommendations & Planning
- Personalized sleep recommendations based on current debt
- Science-based recovery advice (sleep hygiene, circadian rhythm, exercise impact)
- Priority-based recommendation system (HIGH/MEDIUM/LOW)
- Multi-week recovery plan generator
- Weekend recovery opportunity highlighting
- Daily and weekly recovery targets

#### Commands
- `init` - Initialize with 30 days of randomized sample data
- `status` - Display current sleep status and debt
- `log` - Quick sleep entry logging
- `add` - Interactive detailed entry mode
- `recommend` - Get personalized recommendations
- `plan` - Generate recovery schedule (customizable weeks)
- `graph` - Generate and display visualizations
- `calendar` - ASCII calendar view of sleep patterns
- Interactive mode (no arguments) - Unified dashboard

### Technical Details
- Python 3.7+ compatibility
- Cross-platform support (macOS, Linux, Windows)
- Matplotlib 3.5.0+ for visualizations
- No database required (JSON file storage)
- Single-file architecture (~1,700 lines)

### Documentation
- Comprehensive README with usage guide
- Inline code documentation
- Sleep science background information
- Installation and troubleshooting guides
- MIT License

## Future Roadmap

### Planned Features
- [ ] Apple Health / Fitbit integration
- [ ] Sleep quality metrics (deep sleep, REM cycles)
- [ ] Correlation analysis (exercise, caffeine, stress)
- [ ] Export to CSV/PDF reports
- [ ] Weekly email summaries
- [ ] Mobile app version
- [ ] Multi-user support
- [ ] Cloud sync capabilities

### Under Consideration
- [ ] Sleep stage analysis (if wearable data available)
- [ ] Nap tracking
- [ ] Environmental factors (temperature, light, noise)
- [ ] Medication/supplement tracking
- [ ] Dream journal integration
- [ ] Social comparison (anonymized)

---

## Version History

**1.2.0** - Wake time customization & dynamic recommendations (2025-12-28)
**1.1.0** - Profile personalization & enhanced time filtering (2025-12-24)
**1.0.0** - Initial public release (2025-12-18)

Author: Houman Khosravani MD PhD FRCPC
