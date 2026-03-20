"""
Utility functions for schedule module
"""
from datetime import date
from flask import url_for
from app.models import AcademicYear, SchedulePeriod, Schedule, Workload, Room


def is_period_closed(schedule_date):
    """Check if the date falls within a closed schedule period"""
    print(f"DEBUG is_period_closed: Checking date {schedule_date}")
    
    # Get current academic year
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    print(f"DEBUG is_period_closed: Current year = {current_year}")
    if not current_year:
        print("DEBUG is_period_closed: No current academic year found")
        return False
        
    # Find the closed period for this date
    closed_period = SchedulePeriod.query.filter(
        SchedulePeriod.academic_year_id == current_year.id,
        SchedulePeriod.status == 'closed',
        SchedulePeriod.start_date <= schedule_date,
        SchedulePeriod.end_date >= schedule_date
    ).first()
    
    print(f"DEBUG is_period_closed: Found closed period = {closed_period}")
    if closed_period:
        print(f"DEBUG is_period_closed: Period {closed_period.start_date} - {closed_period.end_date}, status = {closed_period.status}")
    
    result = closed_period is not None
    print(f"DEBUG is_period_closed: Returning {result}")
    return result


def perform_detailed_placement_diagnostic(group_id, semester, workload, remaining_hours, hours_per_week, future_gup_weeks, academic_year_id):
    """Performs detailed diagnostic of placement issues"""
    problems = []
    recommendations = []
    today = date.today()
    
    # Analysis 1: Check teacher conflicts
    teacher_conflicts = 0
    teacher_busy_slots = []
    
    if workload.teacher:
        # Get all teacher's future classes
        teacher_schedule = Schedule.query.join(Workload).filter(
            Workload.teacher_id == workload.teacher_id,
            Schedule.date >= today
        ).all()
        
        teacher_conflicts = len(teacher_schedule)
        
        # Analyze time distribution
        time_slots = {}
        for schedule in teacher_schedule:
            time_key = f"pair_{schedule.pair_number}"
            if time_key not in time_slots:
                time_slots[time_key] = 0
            time_slots[time_key] += 1
        
        # Find busiest slots
        if time_slots:
            max_conflicts = max(time_slots.values())
            busy_pairs = [pair.replace('pair_', '') for pair, count in time_slots.items() if count >= max_conflicts * 0.7]
            teacher_busy_slots = busy_pairs
    
    # Analysis 2: Check group conflicts  
    group_conflicts = 0
    group_busy_slots = []
    
    group_schedule = Schedule.query.join(Workload).filter(
        Workload.group_id == group_id,
        Schedule.date >= today
    ).all()
    
    group_conflicts = len(group_schedule)
    
    # Analyze time distribution for group
    group_time_slots = {}
    for schedule in group_schedule:
        time_key = f"pair_{schedule.pair_number}"
        if time_key not in group_time_slots:
            group_time_slots[time_key] = 0
        group_time_slots[time_key] += 1
    
    if group_time_slots:
        max_group_conflicts = max(group_time_slots.values())
        busy_group_pairs = [pair.replace('pair_', '') for pair, count in group_time_slots.items() if count >= max_group_conflicts * 0.7]
        group_busy_slots = busy_group_pairs
    
    # Analysis 3: Check room availability
    total_rooms = Room.query.count()
    room_utilization = 0
    
    if total_rooms > 0:
        # Approximate room utilization assessment
        total_future_classes = Schedule.query.filter(Schedule.date >= today).count()
        room_utilization = (total_future_classes / (total_rooms * future_gup_weeks * 6)) * 100 if future_gup_weeks > 0 else 0
    
    # Analysis 4: Check overlapping busy slots
    common_busy_slots = list(set(teacher_busy_slots) & set(group_busy_slots))
    
    # Form problems based on analysis
    root_cause_found = False
    
    # Cause 1: Critical teacher conflicts
    if teacher_conflicts > future_gup_weeks * 3:  # More than 3 pairs per week
        problems.append({
            'type': 'teacher_overbooked',
            'title': 'Teacher critically overloaded',
            'description': f'Teacher has {teacher_conflicts} classes over {future_gup_weeks} weeks (more than 3 pairs/week). Busiest times: {", ".join(teacher_busy_slots[:3]) if teacher_busy_slots else "all"}',
            'severity': 'critical'
        })
        recommendations.append({
            'type': 'reassign_teacher',
            'title': 'Assign additional teacher',
            'description': f'Current teacher is overloaded. Consider load distribution or assigning second teacher',
            'action_url': url_for('workload.edit', id=workload.id),
            'priority': 'high'
        })
        root_cause_found = True
    
    # Cause 2: Time slot conflicts
    elif common_busy_slots:
        problems.append({
            'type': 'time_slot_conflicts',
            'title': 'Time slot conflicts',
            'description': f'Teacher and group are simultaneously busy in: {", ".join(common_busy_slots[:3])} pairs. Not enough free slots to place {remaining_hours}h',
            'severity': 'error'
        })
        
        # Suggest alternative times
        all_pairs = ['1', '2', '3', '4', '5', '6']
        free_slots = [pair for pair in all_pairs if pair not in common_busy_slots]
        
        recommendations.append({
            'type': 'adjust_schedule_time',
            'title': f'Try placement in {", ".join(free_slots[:2])} pairs' if free_slots else 'Change class times',
            'description': f'Recommended free slots: {", ".join(free_slots)}' if free_slots else 'Redistribute existing classes to free slots',
            'action_url': url_for('schedule.generate'),
            'priority': 'high'
        })
        root_cause_found = True
    
    # Cause 3: Insufficient rooms
    elif total_rooms < 3:
        problems.append({
            'type': 'insufficient_rooms',
            'title': 'Critical room shortage',
            'description': f'System has only {total_rooms} rooms. This creates bottleneck in schedule placement',
            'severity': 'critical'
        })
        recommendations.append({
            'type': 'add_more_rooms',
            'title': 'Add rooms to system',
            'description': 'Minimum rooms for normal operation: 5-7',
            'action_url': url_for('main.index'),
            'priority': 'high'
        })
        root_cause_found = True
    
    # Cause 4: High room utilization
    elif room_utilization > 80:
        problems.append({
            'type': 'room_overutilization',
            'title': 'Rooms are overloaded',
            'description': f'Room utilization: {room_utilization:.1f}%. Not enough free rooms at needed times',
            'severity': 'warning'
        })
        recommendations.append({
            'type': 'optimize_room_usage',
            'title': 'Optimize room usage',
            'description': 'Use "Full replan" mode to redistribute rooms',
            'action_url': url_for('schedule.generate'),
            'priority': 'medium'
        })
        root_cause_found = True
    
    # Cause 5: Dense group schedule
    elif group_conflicts > future_gup_weeks * 4:  # More than 4 pairs per week
        problems.append({
            'type': 'group_schedule_density',
            'title': 'Group schedule too dense',
            'description': f'Group has {group_conflicts} classes over {future_gup_weeks} weeks. Few free slots for new disciplines',
            'severity': 'warning'
        })
        recommendations.append({
            'type': 'redistribute_group_load',
            'title': 'Redistribute group load',
            'description': 'Consider moving some classes to different time or increasing number of weeks',
            'action_url': url_for('gup.index', group_id=group_id),
            'priority': 'medium'
        })
        root_cause_found = True
    
    # If no specific cause found, give general analysis
    if not root_cause_found:
        problems.append({
            'type': 'complex_placement_issue',
            'title': 'Complex placement issue',
            'description': f'Placement blocked by combination of factors: teacher load ({teacher_conflicts} classes), group load ({group_conflicts} classes), {total_rooms} rooms with {room_utilization:.1f}% utilization',
            'severity': 'info'
        })
        
        # Give several solution options
        recommendations.extend([
            {
                'type': 'try_full_replan',
                'title': '"Full replan" mode',
                'description': 'Redistributes all incomplete classes considering optimal time and room usage',
                'action_url': url_for('schedule.generate'),
                'priority': 'high'
            },
            {
                'type': 'increase_weekly_hours_alt',
                'title': f'Increase intensity to {min(remaining_hours // future_gup_weeks + 2, 8)}h/week',
                'description': 'More intensive schedule might help find free slots',
                'action_url': url_for('workload.edit', id=workload.id),
                'priority': 'medium'
            }
        ])
    
    return {
        'problems': problems,
        'recommendations': recommendations
    }


# Global storage for generation progress tracking
generation_progress = {}