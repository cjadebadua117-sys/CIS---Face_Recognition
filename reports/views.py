import csv
import io
from datetime import datetime
from django.http import HttpResponse
from django.shortcuts import redirect
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from attendance.models import AttendanceRecord


def filter_records(request):
    records = AttendanceRecord.objects.select_related('person__department')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    department = request.GET.get('department')
    if date_from:
        records = records.filter(date__gte=date_from)
    if date_to:
        records = records.filter(date__lte=date_to)
    if status:
        records = records.filter(status=status)
    if department:
        records = records.filter(person__department__name__icontains=department)
    return records


def export_attendance_csv(request):
    records = filter_records(request)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Name', 'ID', 'Department', 'Time In', 'Time Out', 'Status'])
    for item in records:
        writer.writerow([
            item.date,
            item.person.name,
            item.person.person_id,
            item.person.department.name if item.person.department else '',
            item.time_in or '',
            item.time_out or '',
            item.get_status_display(),
        ])
    return response


def export_attendance_pdf(request):
    records = filter_records(request)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title='Attendance Export')
    styles = getSampleStyleSheet()
    elements = [Paragraph('Attendance Report', styles['Title']), Spacer(1, 12)]
    data = [['Date', 'Name', 'ID', 'Department', 'Time In', 'Time Out', 'Status']]
    for item in records:
        data.append([
            item.date.strftime('%Y-%m-%d'),
            item.person.name,
            item.person.person_id,
            item.person.department.name if item.person.department else '',
            item.time_in.strftime('%H:%M:%S') if item.time_in else '',
            item.time_out.strftime('%H:%M:%S') if item.time_out else '',
            item.get_status_display(),
        ])
    table = Table(data, repeatRows=1, style=[
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ])
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.pdf"'
    return response
