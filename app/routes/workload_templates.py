from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
import json
from datetime import datetime
from app import db
from app.models import WorkloadTemplate, Group, Workload, GUP, AcademicYear, SchedulePeriod, Schedule
from sqlalchemy import and_
from config import Config
import logging

# Safe print for Windows with Kazakh/Russian characters
def safe_print(msg):
    try:
        print(str(msg))
    except UnicodeEncodeError:
        # Skip output if encoding fails - don't crash the app
        pass

bp = Blueprint('workload_templates', __name__, url_prefix='/workload-templates')


@bp.route('/editor')
@bp.route('/editor/<int:template_id>')
def editor(template_id=None):
    """Workload template editor page"""
    template_data = None
    
    if template_id:
        template = WorkloadTemplate.query.get_or_404(template_id)
        template_data = template.to_dict()
    
    return render_template(
        'workload_templates/editor.html',
        template_data=template_data
    )


# === API ENDPOINTS ===

@bp.route('/api/', methods=['GET'])
def list_templates():
    """List all workload templates with filters"""
    group_id = request.args.get('group_id', type=int)
    semester = request.args.get('semester', type=int)
    academic_year_id = request.args.get('academic_year_id', type=int)
    
    query = WorkloadTemplate.query
    
    if group_id:
        query = query.filter_by(group_id=group_id)
    if semester:
        query = query.filter_by(semester=semester)
    if academic_year_id:
        query = query.filter_by(academic_year_id=academic_year_id)
    
    templates = query.order_by(WorkloadTemplate.created_at.desc()).all()
    
    return jsonify([t.to_dict() for t in templates])


@bp.route('/api/', methods=['POST'])
def create_template():
    """Create new workload template"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'group_id', 'workload_id', 'semester', 'total_hours', 'weeks']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        # Get current academic year
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            return jsonify({'error': 'No current academic year found'}), 400
        
        # Check if template already exists for this workload/group/semester
        existing = WorkloadTemplate.query.filter_by(
            workload_id=data['workload_id'],
            group_id=data['group_id'],
            semester=data['semester']
        ).first()
        
        if existing:
            # Update existing template
            existing.name = data['name']
            existing.total_hours = data['total_hours']
            existing.distribution_json = json.dumps(data['weeks'])
            existing.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'id': existing.id,
                'message': 'Template updated successfully'
            }), 200
        else:
            # Create new template
            template = WorkloadTemplate(
                name=data['name'],
                workload_id=data['workload_id'],
                group_id=data['group_id'],
                academic_year_id=current_year.id,
                semester=data['semester'],
                total_hours=data['total_hours'],
                distribution_json=json.dumps(data['weeks']),
                created_by=session.get('username', 'system')
            )
            
            db.session.add(template)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'id': template.id,
                'message': 'Template created successfully'
            }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/<int:template_id>', methods=['GET'])
def get_template(template_id):
    """Get specific template"""
    template = WorkloadTemplate.query.get_or_404(template_id)
    return jsonify(template.to_dict())


@bp.route('/api/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    """Update existing template"""
    try:
        template = WorkloadTemplate.query.get_or_404(template_id)
        data = request.get_json()
        
        # Check if periods are locked before allowing updates
        if 'weeks' in data:
            locked_weeks = check_locked_periods(data['weeks'], template.academic_year_id)
            if locked_weeks:
                return jsonify({
                    'error': f'Cannot edit template: weeks {", ".join(map(str, locked_weeks))} are locked'
                }), 403
        
        # Update fields
        if 'name' in data:
            template.name = data['name']
        if 'total_hours' in data:
            template.total_hours = data['total_hours']
        if 'weeks' in data:
            template.distribution_json = json.dumps(data['weeks'])
        
        template.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Template updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    """Delete template"""
    try:
        template = WorkloadTemplate.query.get_or_404(template_id)
        
        # Check if periods are locked
        weeks_data = template.weeks_data
        locked_weeks = check_locked_periods(weeks_data, template.academic_year_id)
        if locked_weeks:
            return jsonify({
                'error': f'Cannot delete template: weeks {", ".join(map(str, locked_weeks))} are locked'
            }), 403
        
        db.session.delete(template)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Template deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/groups-with-gup')
def groups_with_gup():
    """Get groups with their GUP data for editor"""
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    if not current_year:
        return jsonify([])
    
    groups = Group.query.order_by(Group.name).all()
    result = []
    
    for group in groups:
        gup_data = GUP.query.filter_by(
            group_id=group.id,
            academic_year_id=current_year.id
        ).order_by(GUP.week_number).all()
        
        gup_weeks = {}
        for gup in gup_data:
            gup_weeks[str(gup.week_number)] = {
                'activity': gup.activity_name or 'Теоретическое обучение',
                'activity_code': gup.activity_code or '',
                'start_date': gup.start_date.isoformat() if gup.start_date else None,
                'end_date': gup.end_date.isoformat() if gup.end_date else None,
                'needs_schedule': gup.needs_schedule
            }
        
        result.append({
            'id': group.id,
            'name': group.name,
            'course': group.course,
            'specialty': group.specialty.name_ru if group.specialty else None,
            'gup': gup_weeks
        })
    
    return jsonify(result)


@bp.route('/api/my-workload')
def get_my_workload():
    """Get existing workload for current academic year"""
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    if not current_year:
        return jsonify([])
    
    # Get all workloads for current academic year
    workloads = Workload.query.filter_by(academic_year_id=current_year.id).order_by(
        Workload.discipline, Workload.group_id, Workload.semester
    ).all()
    
    result = []
    for workload in workloads:
        # Check if template already exists
        existing_template = WorkloadTemplate.query.filter_by(
            workload_id=workload.id,
            group_id=workload.group_id,
            semester=workload.semester
        ).first()
        
        result.append({
            'id': workload.id,
            'discipline': workload.discipline,
            'teacher_id': workload.teacher_id,
            'teacher_name': workload.teacher.full_name if workload.teacher else None,
            'group_id': workload.group_id,
            'group_name': workload.group.name if workload.group else None,
            'total_hours': workload.total_hours,
            'hours_per_week': workload.hours_per_week,
            'semester': workload.semester,
            'lesson_type': workload.lesson_type,
            'has_template': existing_template is not None,
            'template_id': existing_template.id if existing_template else None
        })
    
    return jsonify(result)

@bp.route('/api/semester-weeks/<int:workload_id>/<int:semester>')
def get_semester_weeks(workload_id, semester):
    """Get GUP weeks for specific workload - semester parameter is for compatibility only"""
    workload = Workload.query.get_or_404(workload_id)
    
    # Get ALL GUP weeks for this workload's group and academic year
    gup_weeks = GUP.query.filter_by(
        group_id=workload.group_id,
        academic_year_id=workload.academic_year_id
    ).order_by(GUP.week_number).all()
    
    if not gup_weeks:
        return jsonify([])
    
    # Return ALL actual GUP weeks, let frontend handle filtering
    result = []
    for w in gup_weeks:
        result.append({
            'id': w.id,
            'week_number': w.week_number,
            'start_date': w.start_date.isoformat() if w.start_date else None,
            'end_date': w.end_date.isoformat() if w.end_date else None,
            'activity_code': w.activity_code,
            'activity_name': w.activity_name,
            'needs_schedule': w.needs_schedule
        })
    
    return jsonify(result)

# Keep the old endpoint for backward compatibility  
@bp.route('/api/semester-weeks/<int:workload_id>')
def get_semester_weeks_old(workload_id):
    """Get GUP semester weeks for specific workload (backward compatibility)"""
    return get_semester_weeks(workload_id, 1)  # Default to semester 1

@bp.route('/api/groups-with-workloads')
def groups_with_workloads():
    """Get all groups with their workloads count"""
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    if not current_year:
        return jsonify([])
    
    from app.models import Group
    groups = Group.query.order_by(Group.name).all()
    result = []
    
    for group in groups:
        workloads = Workload.query.filter_by(
            group_id=group.id,
            academic_year_id=current_year.id
        ).all()
        
        result.append({
            'id': group.id,
            'name': group.name,
            'course': group.course,
            'specialty_name': group.specialty.name_ru if group.specialty else None,
            'workloads_count': len(workloads)
        })
    
    return jsonify(result)

@bp.route('/api/workloads-by-group/<int:group_id>')
def workloads_by_group(group_id):
    """Get workloads for specific group"""
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    if not current_year:
        return jsonify([])
    
    workloads = Workload.query.filter_by(
        group_id=group_id,
        academic_year_id=current_year.id
    ).order_by(Workload.discipline).all()
    
    result = []
    for workload in workloads:
        # Check if template already exists
        existing_template = WorkloadTemplate.query.filter_by(
            workload_id=workload.id,
            group_id=group_id,
            semester=workload.semester
        ).first()
        
        result.append({
            'id': workload.id,
            'discipline': workload.discipline,
            'teacher_id': workload.teacher_id,
            'teacher_name': workload.teacher.full_name if workload.teacher else None,
            'total_hours': workload.total_hours,
            'hours_per_week': workload.hours_per_week,
            'semester': workload.semester,
            'lesson_type': workload.lesson_type,
            'has_template': existing_template is not None,
            'template_id': existing_template.id if existing_template else None
        })
    
    return jsonify(result)


@bp.route('/api/template-constraints/<int:template_id>')
def get_template_constraints(template_id):
    """Get slot constraints for scheduler from template"""
    template = WorkloadTemplate.query.get_or_404(template_id)
    constraints = template.get_slot_constraints()
    
    return jsonify(constraints)


def check_locked_periods(weeks_data, academic_year_id):
    """Check if any weeks in the template are locked"""
    locked_weeks = []
    
    for week_data in weeks_data:
        week_num = week_data.get('week')
        if not week_num:
            continue
            
        period = SchedulePeriod.query.filter_by(
            academic_year_id=academic_year_id,
            week_number=week_num
        ).first()
        
        if period and period.is_locked:
            locked_weeks.append(week_num)
    
    return locked_weeks


@bp.route('/api/preview-schedule', methods=['POST'])
def preview_schedule():
    """Get schedule preview data with template overlay"""
    from app.models import Schedule, Teacher, Room as Classroom, GUP
    from datetime import datetime, timedelta
    # Force reload - updated at 00:58
    
    try:
        safe_print("Preview schedule API called")
        data = request.get_json()
        safe_print(f"Request data received: {data}")
        
        if not data:
            safe_print("No JSON data received")
            return jsonify({'error': 'No JSON data received'}), 400

        group_id = data.get('group_id')
        template_data = data.get('template_data', {})
        safe_print(f"Group ID: {group_id}, Template data keys: {template_data.keys()}")
        
        if not group_id:
            return jsonify({'error': 'group_id is required'}), 400
            
        # Get group info
        group = Group.query.get(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
            
        # Get current academic year
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        if not current_year:
            return jsonify({'error': 'No current academic year found'}), 400
            
        # Get existing schedule for this group (join through workload)
        from app.models import Workload
        existing_schedule = Schedule.query.join(Workload).filter(Workload.group_id == group_id).all()
        
        # Convert to dict for easy lookup: {(date, pair_number): schedule_entry}
        schedule_dict = {}
        for entry in existing_schedule:
            date_key = entry.date.strftime('%Y-%m-%d')
            schedule_dict[(date_key, entry.pair_number)] = {
                'id': entry.id,
                'discipline': entry.workload.discipline if entry.workload else 'Не определена',
                'teacher': entry.workload.teacher.full_name if entry.workload and entry.workload.teacher else 'Не назначен',
                'classroom': entry.room.number if entry.room else 'Не назначена',
                'type': entry.workload.lesson_type if entry.workload else 'theory',
                'status': entry.status
            }
            
        # Get GUP data for academic year
        gup_data = GUP.query.filter_by(academic_year_id=current_year.id).all()
        
        # Convert template data to schedule entries
        template_schedule = []
        conflicts = []
        
        # Extract weeks data from template_data
        weeks_data_dict = template_data.get('weeks', {})
        safe_print(f"Weeks data found: {len(weeks_data_dict)} weeks")
        
        for week_str, week_data in weeks_data_dict.items():
            try:
                week_number = int(week_str)
            except (ValueError, TypeError):
                continue
                
            # Find GUP entry for this week
            gup_week = next((g for g in gup_data if g.week_number == week_number), None)
            if not gup_week or not gup_week.needs_schedule:
                continue
                
            # Calculate dates for this week
            week_start = gup_week.start_date
            
            for day_str, day_data in week_data.items():
                try:
                    day_index = int(day_str)  # 0=Mon, 1=Tue, etc.
                except (ValueError, TypeError):
                    continue
                    
                if day_index >= 5:  # Only weekdays
                    continue
                    
                current_date = week_start + timedelta(days=day_index)
                date_key = current_date.strftime('%Y-%m-%d')
                
                for pair_str, status in day_data.items():
                    if status != 'selected':
                        continue
                        
                    try:
                        pair_number = int(pair_str)
                    except (ValueError, TypeError):
                        continue
                        
                    # Check for conflicts
                    conflict_info = None
                    existing_entry = schedule_dict.get((date_key, pair_number))
                    
                    if existing_entry:
                        conflict_info = {
                            'type': 'existing_schedule',
                            'details': f"Уже занято: {existing_entry['discipline']} ({existing_entry['teacher']})"
                        }
                    else:
                        # Check teacher conflicts (if we had teacher assignment)
                        # Check classroom conflicts (if we had classroom assignment)
                        # For now, just mark as available
                        pass
                    
                    template_entry = {
                        'date': date_key,
                        'day_name': current_date.strftime('%A'),
                        'pair_number': pair_number,
                        'week_number': week_number,
                        'conflict': conflict_info,
                        'status': 'available' if not conflict_info else 'conflict'
                    }
                    
                    template_schedule.append(template_entry)
                    
                    if conflict_info:
                        conflicts.append(template_entry)
        
        # Prepare week view data (similar to main schedule)
        weeks_data = []
        for week_number in sorted(set(entry['week_number'] for entry in template_schedule)):
            gup_week = next((g for g in gup_data if g.week_number == week_number), None)
            if gup_week:
                weeks_data.append({
                    'week_number': week_number,
                    'start_date': gup_week.start_date.strftime('%Y-%m-%d'),
                    'end_date': gup_week.end_date.strftime('%Y-%m-%d'),
                    'needs_schedule': gup_week.needs_schedule
                })
        
        # Convert schedule_dict to JSON-serializable format
        existing_schedule_list = []
        for (date_key, pair_number), entry_data in schedule_dict.items():
            existing_schedule_list.append({
                'date': date_key,
                'pair_number': pair_number,
                **entry_data  # Spread the existing entry data
            })

        return jsonify({
            'success': True,
            'group': {
                'id': group.id,
                'name': group.name,
                'course': group.course
            },
            'existing_schedule': existing_schedule_list,
            'template_schedule': template_schedule,
            'conflicts': conflicts,
            'weeks_data': weeks_data,
            'pair_times': Config.PAIR_TIMES,  # Add pair times for proper display
            'summary': {
                'total_slots': len(template_schedule),
                'conflicts': len(conflicts),
                'available': len(template_schedule) - len(conflicts),
                'quality_score': max(0, min(100, round((len(template_schedule) - len(conflicts)) / max(1, len(template_schedule)) * 100)))
            }
        })
        
    except Exception as e:
        safe_print(f"Preview schedule error: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

def convert_template_to_schedule_entries(weeks_data, workload, group_id):
    """Convert template weeks_data to schedule entries format for display"""
    from datetime import datetime, timedelta
    
    schedule_entries = []
    
    # Get current academic year and GUP data
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    if not current_year:
        return schedule_entries
        
    gup_data = GUP.query.filter_by(
        group_id=group_id, 
        academic_year_id=current_year.id
    ).all()
    
    # Create a mapping of week numbers to GUP weeks
    gup_weeks = {gup.week_number: gup for gup in gup_data}
    
    safe_print(f"==== TEMPLATE CONVERSION START ====")
    safe_print(f"Converting template data for {len(weeks_data)} weeks")
    safe_print(f"Available GUP weeks: {sorted(gup_weeks.keys())}")
    
    # Посмотрим на первые 2 недели шаблона
    for i, week_data in enumerate(weeks_data[:2]):
        safe_print(f"Week {i}: {week_data}")
    
    # Process each week in the template
    for week_data in weeks_data:
        if not isinstance(week_data, dict) or 'week' not in week_data:
            continue
            
        week_number = week_data.get('week')
        if not week_number:
            continue
            
        # Get the corresponding GUP week
        gup_week = gup_weeks.get(week_number)
        if not gup_week:
            safe_print(f"DEBUG: No GUP data for week {week_number}")
            continue
        if not gup_week.start_date:
            safe_print(f"DEBUG: GUP week {week_number} has no start_date")
            continue
        if not gup_week.needs_schedule:
            safe_print(f"DEBUG: GUP week {week_number} does not need schedule")
            continue
            
        week_start = gup_week.start_date
        
        # Get preferences from week data
        preferences = week_data.get('preferences', {})
        
        # Process each day of the week (0=Monday, 1=Tuesday, etc.)
        for day_index in range(5):  # Only weekdays
            if str(day_index) not in preferences:
                continue
                
            day_data = preferences[str(day_index)]
            if not isinstance(day_data, dict):
                continue
                
            # Calculate the date for this day
            current_date = week_start + timedelta(days=day_index)
            
            # Process each pair for this day
            for pair_str, status in day_data.items():
                if not pair_str.isdigit() or status != 'selected':
                    continue
                    
                pair_number = int(pair_str)
                
                # Create a schedule entry
                schedule_entry = {
                    'date': current_date.strftime('%Y-%m-%d'),
                    'pair_number': pair_number,
                    'discipline': workload.discipline,
                    'teacher': {
                        'name': workload.teacher.full_name if workload.teacher else 'Не назначен'
                    },
                    'room': {
                        'number': 'По расписанию'  # Template doesn't have room assignment yet
                    },
                    'status': 'template'  # Special status for template entries
                }
                
                schedule_entries.append(schedule_entry)
    
    safe_print(f"DEBUG: Created {len(schedule_entries)} template schedule entries")
    if schedule_entries:
        safe_print(f"DEBUG: Sample template entries: {schedule_entries[:3]}")

        # Простая проверка первой недели
        first_week = [e for e in schedule_entries if '2026-01-12' <= e['date'] <= '2026-01-18']
        safe_print(f"DEBUG: Week 12-18 Jan entries: {len(first_week)}")
        for entry in first_week[:8]:  # Первые 8 записей
            safe_print(f"  {entry['date']} pair {entry['pair_number']}")

        # Группируем по дням недели для этой недели
        by_date = {}
        for entry in first_week:
            date = entry['date']
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(entry['pair_number'])

        safe_print("DEBUG: Week 12-18 Jan pairs by date:")
        for date in sorted(by_date.keys()):
            pairs = sorted(by_date[date])
            safe_print(f"  {date}: {pairs} ({len(pairs)} pairs)")
    
    return schedule_entries


@bp.route('/preview/<int:group_id>/<int:workload_id>')
def preview_page(group_id, workload_id):
    """Страница предварительного просмотра шаблонов"""
    try:
        # Get group info
        group = Group.query.get_or_404(group_id)
        workload = Workload.query.get_or_404(workload_id)
        
        # Get current academic year (optional for preview)
        current_year = AcademicYear.query.filter_by(is_current=True).first()
            
        # Get existing schedule for this group with error handling
        existing_schedule_data = []
        try:
            safe_print(f"DEBUG: Querying schedule for group_id={group_id}")

            # First check if there are any schedules at all
            all_schedules = Schedule.query.count()
            safe_print(f"DEBUG: Total schedules in DB: {all_schedules}")

            # Check if there are any workloads for this group
            group_workloads = Workload.query.filter_by(group_id=group_id).all()
            safe_print(f"DEBUG: Workloads for group {group_id}: {len(group_workloads)}")
            for w in group_workloads[:3]:  # Show first 3
                safe_print(f"DEBUG: Workload {w.id}: {w.discipline}, teacher: {w.teacher.full_name if w.teacher else 'None'}")

            existing_schedule = Schedule.query.join(Workload).filter(
                Workload.group_id == group_id
            ).all()
            safe_print(f"DEBUG: Found {len(existing_schedule)} schedule entries for group")
            
            # Convert existing schedule to list of dicts
            for entry in existing_schedule:
                try:
                    existing_schedule_data.append({
                        'date': entry.date.strftime('%Y-%m-%d'),
                        'pair_number': entry.pair_number,
                        'discipline': entry.workload.discipline if entry.workload else 'Не определена',
                        'teacher': {
                            'name': entry.workload.teacher.full_name if entry.workload and entry.workload.teacher else 'Не назначен',
                            'id': entry.workload.teacher.id if entry.workload and entry.workload.teacher else None
                        },
                        'group': {
                            'name': entry.workload.group.name if entry.workload and entry.workload.group else 'Не определена',
                            'id': entry.workload.group.id if entry.workload and entry.workload.group else None
                        },
                        'room': {
                            'number': entry.room.number if entry.room else 'Не назначена'
                        },
                        'status': entry.status or 'planned'
                    })
                except Exception as e:
                    safe_print(f"Error processing schedule entry {entry.id}: {e}")
                    continue
        except Exception as e:
            safe_print(f"Error loading schedule for group {group_id}: {e}")
            existing_schedule_data = []

        safe_print(f"DEBUG: Preview page for group {group.name} (ID: {group_id}), workload {workload.discipline}")
        safe_print(f"DEBUG: Found {len(existing_schedule_data)} schedule entries")
        if existing_schedule_data:
            safe_print(f"DEBUG: Sample entries: {existing_schedule_data[:3]}")

        # Get template data if exists
        template_schedule_data = []
        existing_template = WorkloadTemplate.query.filter_by(
            workload_id=workload_id,
            group_id=group_id
        ).first()

        safe_print(f"DEBUG: Searching for template with workload_id={workload_id}, group_id={group_id}")

        if existing_template:
            safe_print(f"DEBUG: Found template ID {existing_template.id}, name: {existing_template.name}")
            safe_print(f"DEBUG: Template distribution_json: {existing_template.distribution_json}")

            # Get weeks_data property
            weeks_data = existing_template.weeks_data
            safe_print(f"DEBUG: weeks_data type: {type(weeks_data)}, content: {weeks_data[:2] if weeks_data and len(weeks_data) > 0 else 'empty'}")

            if weeks_data:
                safe_print(f"DEBUG: Found template with {len(weeks_data)} weeks")
                # Convert weeks_data to schedule entries format
                template_schedule_data = convert_template_to_schedule_entries(weeks_data, workload, group_id)
                safe_print(f"DEBUG: Converted to {len(template_schedule_data)} schedule entries")
            else:
                safe_print("DEBUG: Template found but weeks_data is empty")
        else:
            safe_print("DEBUG: No template found for this workload")
        
        return render_template('workload_templates/preview.html',
                             group=group,
                             workload=workload,
                             existing_schedule=existing_schedule_data,
                             template_schedule=template_schedule_data)
                             
    except Exception as e:
        flash(f'Ошибка загрузки предпросмотра: {str(e)}', 'error')
        return redirect(url_for('workload_templates.editor'))


@bp.route('/api/groups')
def api_groups():
    """Get all groups for filters"""
    try:
        from app.models import Group
        groups = Group.query.order_by(Group.name).all()
        return jsonify([{
            'id': group.id,
            'name': group.name,
            'course': group.course
        } for group in groups])
    except Exception as e:
        safe_print(f"DEBUG: Error loading groups: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/teachers')
def api_teachers():
    """Get all teachers for filters"""
    try:
        from app.models import Teacher
        teachers = Teacher.query.order_by(Teacher.full_name).all()
        return jsonify([{
            'id': teacher.id,
            'full_name': teacher.full_name
        } for teacher in teachers])
    except Exception as e:
        safe_print(f"DEBUG: Error loading teachers: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/schedule-by-period')
def api_schedule_by_period():
    """Get schedule for a group/teacher within a date range"""
    from datetime import datetime

    try:
        group_id = request.args.get('group_id', type=int)
        teacher_id = request.args.get('teacher_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if not start_date or not end_date:
            return jsonify({'error': 'start_date and end_date are required'}), 400

        # Parse dates
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Build query
        query = Schedule.query.join(Workload).filter(
            Schedule.date >= start,
            Schedule.date <= end
        )

        if group_id:
            query = query.filter(Workload.group_id == group_id)
        elif teacher_id:
            query = query.filter(Workload.teacher_id == teacher_id)
        else:
            return jsonify({'error': 'group_id or teacher_id is required'}), 400

        schedules = query.order_by(Schedule.date, Schedule.pair_number).all()

        result = []
        for s in schedules:
            result.append({
                'id': s.id,
                'date': s.date.strftime('%Y-%m-%d'),
                'pair_number': s.pair_number,
                'discipline': s.workload.discipline if s.workload else 'N/A',
                'status': s.status,
                'teacher': {
                    'id': s.workload.teacher.id,
                    'name': s.workload.teacher.full_name
                } if s.workload and s.workload.teacher else None,
                'room': {
                    'id': s.room.id if s.room else None,
                    'number': s.room.number if s.room else None
                },
                'group': {
                    'id': s.workload.group.id,
                    'name': s.workload.group.name
                } if s.workload and s.workload.group else None
            })

        return jsonify(result)

    except Exception as e:
        safe_print(f"Error in api_schedule_by_period: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/week-type/<int:week_number>')
def api_week_type(week_number):
    """Get week type (left/right) based on academic calendar"""
    # Based on the alternating pattern:
    # Left weeks (Қыс): odd weeks starting from week 1
    # Right weeks (Жаз): even weeks
    # Week 20 starts 2nd semester

    # For 2nd semester (weeks 20+):
    # Week 20 = left, Week 21 = right, Week 22 = left, etc.
    is_left_week = (week_number % 2 == 0)  # Even weeks are left in 2nd semester

    return jsonify({
        'week_number': week_number,
        'week_type': 'left' if is_left_week else 'right',
        'week_type_kz': 'Қыс' if is_left_week else 'Жаз',
        'week_type_ru': 'Левая' if is_left_week else 'Правая'
    })


@bp.route('/api/workloads-with-templates/<int:group_id>')
def workloads_with_templates(group_id):
    """Get all workloads for a group with their existing templates"""
    current_year = AcademicYear.query.filter_by(is_current=True).first()
    if not current_year:
        return jsonify([])

    workloads = Workload.query.filter_by(
        group_id=group_id,
        academic_year_id=current_year.id
    ).order_by(Workload.discipline).all()

    result = []
    for workload in workloads:
        # Get all templates for this workload
        templates = WorkloadTemplate.query.filter_by(
            workload_id=workload.id,
            group_id=group_id
        ).all()

        result.append({
            'id': workload.id,
            'discipline': workload.discipline,
            'teacher_id': workload.teacher_id,
            'teacher_name': workload.teacher.full_name if workload.teacher else None,
            'total_hours': workload.total_hours,
            'hours_per_week': workload.hours_per_week,
            'semester': workload.semester,
            'lesson_type': workload.lesson_type,
            'templates': [{
                'id': t.id,
                'name': t.name,
                'semester': t.semester,
                'weeks_count': len(t.weeks_data) if t.weeks_data else 0,
                'created_at': t.created_at.isoformat() if t.created_at else None
            } for t in templates]
        })

    return jsonify(result)


@bp.route('/api/load-template/<int:template_id>')
def load_template_data(template_id):
    """Load full template data for editing"""
    template = WorkloadTemplate.query.get_or_404(template_id)

    return jsonify({
        'id': template.id,
        'name': template.name,
        'workload_id': template.workload_id,
        'group_id': template.group_id,
        'semester': template.semester,
        'total_hours': template.total_hours,
        'weeks_data': template.weeks_data,
        'workload': {
            'discipline': template.workload.discipline if template.workload else None,
            'teacher_name': template.workload.teacher.full_name if template.workload and template.workload.teacher else None,
            'total_hours': template.workload.total_hours if template.workload else None
        }
    })


@bp.route('/api/teacher-schedule/<int:teacher_id>')
def api_teacher_schedule(teacher_id):
    """Get all schedule entries for a specific teacher"""
    try:
        from app.models import Teacher, Schedule, Workload
        
        teacher = Teacher.query.get_or_404(teacher_id)
        
        # Загружаем все занятия преподавателя через Workload
        schedules = Schedule.query.join(Workload).filter(
            Workload.teacher_id == teacher_id
        ).all()
        
        safe_print(f"DEBUG: Found {len(schedules)} schedule entries for teacher {teacher.full_name}")

        # Convert to list of dicts
        schedule_data = []
        for entry in schedules:
            try:
                schedule_data.append({
                    'date': entry.date.strftime('%Y-%m-%d'),
                    'pair_number': entry.pair_number,
                    'discipline': entry.workload.discipline if entry.workload else 'Не определена',
                    'teacher': {
                        'name': entry.workload.teacher.full_name if entry.workload and entry.workload.teacher else 'Не назначен',
                        'id': entry.workload.teacher.id if entry.workload and entry.workload.teacher else None
                    },
                    'group': {
                        'name': entry.workload.group.name if entry.workload and entry.workload.group else 'Не определена',
                        'id': entry.workload.group.id if entry.workload and entry.workload.group else None
                    },
                    'room': {
                        'number': entry.room.number if entry.room else 'Не назначена'
                    },
                    'status': entry.status or 'planned'
                })
            except Exception as e:
                safe_print(f"Error processing schedule entry {entry.id}: {e}")
                continue

        return jsonify(schedule_data)

    except Exception as e:
        safe_print(f"DEBUG: Error loading teacher schedule: {e}")
        return jsonify({'error': str(e)}), 500