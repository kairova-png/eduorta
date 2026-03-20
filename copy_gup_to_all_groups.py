#!/usr/bin/env python
"""Copy GUP data to all groups that don't have it"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Group, GUP, AcademicYear

app = create_app()


def copy_gup_to_groups():
    with app.app_context():
        print("=" * 80)
        print("COPYING GUP DATA TO ALL GROUPS")
        print("=" * 80)

        # Get current academic year
        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not academic_year:
            academic_year = AcademicYear.query.first()
        print(f"\nAcademic year: {academic_year.name} (id={academic_year.id})")

        # Get all groups by course
        all_groups = Group.query.all()

        # Group by course
        groups_by_course = {}
        for group in all_groups:
            course = group.course
            if course not in groups_by_course:
                groups_by_course[course] = []
            groups_by_course[course].append(group)

        print(f"\nGroups by course:")
        for course in sorted(groups_by_course.keys()):
            print(f"  Course {course}: {len(groups_by_course[course])} groups")

        # Check which groups have GUP
        print("\n" + "=" * 80)
        print("CHECKING GUP STATUS BY COURSE")
        print("=" * 80)

        for course in sorted(groups_by_course.keys()):
            groups = groups_by_course[course]
            print(f"\n--- Course {course} ({len(groups)} groups) ---")

            # Find groups with and without GUP
            groups_with_gup = []
            groups_without_gup = []

            for group in groups:
                gup_count = GUP.query.filter_by(
                    group_id=group.id,
                    academic_year_id=academic_year.id
                ).count()

                if gup_count > 0:
                    groups_with_gup.append((group, gup_count))
                else:
                    groups_without_gup.append(group)

            print(f"  With GUP: {len(groups_with_gup)}")
            for group, count in groups_with_gup[:5]:
                print(f"    - {group.name} ({count} weeks)")
            if len(groups_with_gup) > 5:
                print(f"    ... and {len(groups_with_gup) - 5} more")

            print(f"  Without GUP: {len(groups_without_gup)}")
            for group in groups_without_gup[:10]:
                print(f"    - {group.name}")
            if len(groups_without_gup) > 10:
                print(f"    ... and {len(groups_without_gup) - 10} more")

            # Copy GUP if needed
            if groups_without_gup and groups_with_gup:
                # Use the first group with GUP as source
                source_group, source_count = groups_with_gup[0]
                print(f"\n  Copying GUP from {source_group.name} to {len(groups_without_gup)} groups...")

                # Get source GUP data
                source_gup = GUP.query.filter_by(
                    group_id=source_group.id,
                    academic_year_id=academic_year.id
                ).all()

                copied = 0
                for target_group in groups_without_gup:
                    for gup in source_gup:
                        new_gup = GUP(
                            group_id=target_group.id,
                            academic_year_id=academic_year.id,
                            week_number=gup.week_number,
                            start_date=gup.start_date,
                            end_date=gup.end_date,
                            activity_code=gup.activity_code,
                            activity_name=gup.activity_name
                        )
                        db.session.add(new_gup)
                    copied += 1
                    print(f"    + {target_group.name}")

                db.session.commit()
                print(f"  Copied GUP to {copied} groups")

            elif groups_without_gup and not groups_with_gup:
                print(f"\n  WARNING: No source GUP found for course {course}!")
                print(f"  Need to find GUP from another course or create manually")

        # Final summary
        print("\n" + "=" * 80)
        print("FINAL STATUS")
        print("=" * 80)

        for course in sorted(groups_by_course.keys()):
            groups = groups_by_course[course]
            groups_with_gup = 0
            groups_without_gup = 0

            for group in groups:
                gup_count = GUP.query.filter_by(
                    group_id=group.id,
                    academic_year_id=academic_year.id
                ).count()
                if gup_count > 0:
                    groups_with_gup += 1
                else:
                    groups_without_gup += 1

            status = "✓" if groups_without_gup == 0 else "✗"
            print(f"  Course {course}: {groups_with_gup}/{len(groups)} with GUP {status}")


if __name__ == "__main__":
    copy_gup_to_groups()
