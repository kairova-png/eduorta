#!/usr/bin/env python
"""Export GUP data for 1st course, weeks 20-41 to JSON"""

import json
import os
import sys
from datetime import datetime, timedelta

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Group, GUP, AcademicYear

app = create_app()

def get_week_dates(start_date, end_date):
    """Generate list of dates for a week with day names"""
    dates = []
    current = start_date
    day_names = {
        0: "Monday",
        1: "Tuesday",
        2: "Wednesday",
        3: "Thursday",
        4: "Friday",
        5: "Saturday",
        6: "Sunday"
    }
    day_names_ru = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье"
    }

    while current <= end_date:
        dates.append({
            "date": current.strftime("%Y-%m-%d"),
            "day_of_week": current.weekday(),
            "day_name": day_names[current.weekday()],
            "day_name_ru": day_names_ru[current.weekday()],
            "can_schedule": current.weekday() < 6  # Not Sunday by default
        })
        current += timedelta(days=1)

    return dates

def export_gup_data():
    with app.app_context():
        # Get current academic year
        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not academic_year:
            academic_year = AcademicYear.query.first()

        print(f"Academic year: {academic_year.name if academic_year else 'Not found'}")

        # Get 1st course groups (enrolled in 2025 for academic year 2025-2026)
        # Since current year is 2026, 1st course = enrollment_year 2025
        first_course_groups = Group.query.filter(Group.enrollment_year == 2025).all()

        if not first_course_groups:
            # Try to find any groups and check their course property
            all_groups = Group.query.all()
            first_course_groups = [g for g in all_groups if g.course == 1]

        print(f"Found {len(first_course_groups)} first course groups")

        # Activity codes that BLOCK scheduling
        blocking_codes = {
            "К": "Каникулы (Holidays)",
            "П": "Практика (Practice)",
            "ДА": "Дипломная аттестация (Diploma certification)",
            "Э": "Экзамены (Exams)",
            "ГЭ": "Государственные экзамены (State exams)",
            "ИА": "Итоговая аттестация (Final certification)",
            "ПА": "Промежуточная аттестация (Mid-term certification)"
        }

        # Activity codes that ALLOW scheduling
        allowed_codes = {
            "": "Теоретическое обучение (Theory)",
            None: "Теоретическое обучение (Theory)",
            "None": "Теоретическое обучение (Theory)",
            "УП": "Учебная практика (Training practice)",
            "ОТ": "Теоретическое обучение (Theory)",
            "ӨО": "Теоретическое обучение (Theory - Kazakh)"
        }

        result = {
            "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "academic_year": academic_year.name if academic_year else "Unknown",
            "course": 1,
            "week_range": {"from": 20, "to": 41},
            "description": "GUP data for 1st course students, weeks 20-41",
            "legend": {
                "can_schedule": "Days when classes CAN be scheduled",
                "cannot_schedule": "Days when classes CANNOT be scheduled (holidays, exams, practice, etc.)",
                "activity_codes": {
                    "blocking": blocking_codes,
                    "allowed": allowed_codes
                }
            },
            "groups": [],
            "weeks": []
        }

        # Add group info
        for group in first_course_groups:
            result["groups"].append({
                "id": group.id,
                "name": group.name,
                "specialty_code": group.specialty.code if group.specialty else None,
                "shift": group.shift,
                "shift_name": group.shift_name
            })

        # Get GUP data for weeks 20-41
        # We'll use the first group as reference (all 1st course groups have same GUP)
        if first_course_groups:
            reference_group = first_course_groups[0]

            for week_num in range(20, 42):  # 20 to 41 inclusive
                gup_entry = GUP.query.filter_by(
                    group_id=reference_group.id,
                    week_number=week_num
                ).first()

                if gup_entry:
                    can_schedule = gup_entry.needs_schedule
                    activity_code = gup_entry.activity_code or ""
                    activity_name = gup_entry.activity_name or ""

                    # Get dates for this week
                    week_dates = []
                    if gup_entry.start_date and gup_entry.end_date:
                        week_dates = get_week_dates(gup_entry.start_date, gup_entry.end_date)
                        # Update can_schedule based on GUP activity
                        for date_info in week_dates:
                            if not can_schedule:
                                date_info["can_schedule"] = False
                                date_info["blocked_reason"] = activity_name or activity_code

                    week_data = {
                        "week_number": week_num,
                        "start_date": gup_entry.start_date.strftime("%Y-%m-%d") if gup_entry.start_date else None,
                        "end_date": gup_entry.end_date.strftime("%Y-%m-%d") if gup_entry.end_date else None,
                        "activity_code": activity_code,
                        "activity_name": activity_name,
                        "can_schedule_classes": can_schedule,
                        "status": "available" if can_schedule else "blocked",
                        "dates": week_dates
                    }
                else:
                    week_data = {
                        "week_number": week_num,
                        "start_date": None,
                        "end_date": None,
                        "activity_code": None,
                        "activity_name": "No GUP data",
                        "can_schedule_classes": False,
                        "status": "no_data",
                        "dates": []
                    }

                result["weeks"].append(week_data)

        # Summary statistics
        available_weeks = sum(1 for w in result["weeks"] if w["can_schedule_classes"])
        blocked_weeks = len(result["weeks"]) - available_weeks

        result["summary"] = {
            "total_weeks": len(result["weeks"]),
            "available_weeks": available_weeks,
            "blocked_weeks": blocked_weeks,
            "total_available_days": sum(
                sum(1 for d in w["dates"] if d.get("can_schedule", False))
                for w in result["weeks"]
            )
        }

        return result

if __name__ == "__main__":
    data = export_gup_data()

    # Save to file
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "exports",
        "gup_course1_weeks20_41.json"
    )

    # Create exports directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nExported to: {output_path}")
    print(f"\nSummary:")
    print(f"  Academic year: {data['academic_year']}")
    print(f"  Groups: {len(data['groups'])}")
    print(f"  Total weeks: {data['summary']['total_weeks']}")
    print(f"  Available weeks: {data['summary']['available_weeks']}")
    print(f"  Blocked weeks: {data['summary']['blocked_weeks']}")
    print(f"  Total available days: {data['summary']['total_available_days']}")
