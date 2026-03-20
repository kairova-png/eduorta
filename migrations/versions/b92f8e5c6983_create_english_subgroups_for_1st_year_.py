"""Create English subgroups for 1st year students

Revision ID: b92f8e5c6983
Revises: 13c3347ecf35
Create Date: 2026-01-05 17:02:39.399561

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b92f8e5c6983'
down_revision = '13c3347ecf35'
branch_labels = None
depends_on = None


def upgrade():
    # Get connection to execute raw SQL
    connection = op.get_bind()
    
    # Create English subgroups for all 1st year groups (course = 1)
    # This will create groups with 'б' suffix for English classes
    
    # Current year - groups where (current_year - enrollment_year) = 1 are 1st year students
    # For 2026, 1st year students enrolled in 2025
    current_year = 2026
    first_year_enrollment = current_year - 1
    
    sql_create_subgroups = f"""
    INSERT INTO groups (name, specialty_id, group_number, enrollment_year, shift, max_consecutive_pairs)
    SELECT 
        CONCAT(name, 'б') as name,
        specialty_id,
        group_number,
        enrollment_year,
        shift,
        max_consecutive_pairs
    FROM groups 
    WHERE enrollment_year = {first_year_enrollment}
    AND name NOT LIKE '%б'
    """
    
    connection.execute(sa.text(sql_create_subgroups))
    print("Created English subgroups for all 1st year students")


def downgrade():
    # Remove English subgroups (groups ending with 'б')
    connection = op.get_bind()
    
    current_year = 2026
    first_year_enrollment = current_year - 1
    
    sql_remove_subgroups = f"""
    DELETE FROM groups 
    WHERE name LIKE '%б' 
    AND enrollment_year = {first_year_enrollment}
    """
    
    connection.execute(sa.text(sql_remove_subgroups))
    print("Removed English subgroups")
