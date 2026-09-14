import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.platypus.flowables import KeepTogether
from reportlab.lib.units import inch

styles = getSampleStyleSheet()

# Custom Styles
title_style = ParagraphStyle('MainTitle', fontName='Helvetica-Bold', fontSize=26, spaceAfter=20, textColor=colors.HexColor('#0d233a'), alignment=1)
subtitle_style = ParagraphStyle('Sub', fontName='Helvetica', fontSize=16, textColor=colors.grey, alignment=1)
h1 = ParagraphStyle('Heading1Custom', fontName='Helvetica-Bold', fontSize=18, spaceBefore=20, spaceAfter=10, textColor=colors.HexColor('#1f497d'))
h2 = ParagraphStyle('Heading2Custom', fontName='Helvetica-Bold', fontSize=14, spaceBefore=15, spaceAfter=8, textColor=colors.HexColor('#2f5496'))
normal = ParagraphStyle('NormalCustom', fontName='Helvetica', fontSize=11, spaceAfter=8, leading=15)
bullet = ParagraphStyle('BulletCustom', fontName='Helvetica', fontSize=11, spaceAfter=4, leading=15, leftIndent=15)

def create_arrow(x, y, height):
    return [
        Line(x, y, x, y - height + 6, strokeWidth=2, strokeColor=colors.grey),
        Polygon([x-4, y - height + 6, x+4, y - height + 6, x, y - height], fillColor=colors.grey, strokeColor=colors.grey)
    ]

def draw_architecture_diagram():
    d = Drawing(450, 420)
    
    # 1. Client Layer (y=360 to 400)
    d.add(Rect(25, 360, 400, 40, fillColor=colors.HexColor('#d9e1f2'), strokeColor=colors.HexColor('#2f5496'), radius=4))
    d.add(String(225, 375, "Presentation Layer (Dashboard UI, Vanilla JS, API Polling)", fontSize=12, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.black))
    
    # Arrow down
    for s in create_arrow(225, 360, 40): d.add(s)
    
    # 2. API Layer (y=280 to 320)
    d.add(Rect(25, 280, 400, 40, fillColor=colors.HexColor('#e8d1ff'), strokeColor=colors.HexColor('#7030a0'), radius=4))
    d.add(String(225, 295, "API Gateway (FastAPI, Uvicorn, Timing-Safe Auth)", fontSize=12, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.black))
    
    for s in create_arrow(225, 280, 40): d.add(s)

    # 3. Processing Layer (y=170 to 240)
    d.add(Rect(25, 170, 400, 70, fillColor=colors.HexColor('#fff2cc'), strokeColor=colors.HexColor('#bf8f00'), radius=4))
    d.add(String(225, 220, "Core Processing & AI Engine Layer", fontSize=12, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.black))
    
    # Inner boxes
    d.add(Rect(40, 180, 170, 30, fillColor=colors.white, strokeColor=colors.grey, radius=2))
    d.add(String(125, 190, "StreamWorkerPool (FFmpeg)", fontSize=10, fontName='Helvetica', textAnchor='middle', fillColor=colors.black))
    d.add(Rect(240, 180, 170, 30, fillColor=colors.white, strokeColor=colors.grey, radius=2))
    d.add(String(325, 190, "Vision Engine (YOLOv8 + OCR)", fontSize=10, fontName='Helvetica', textAnchor='middle', fillColor=colors.black))

    for s in create_arrow(225, 170, 40): d.add(s)

    # 4. Data Layer (y=90 to 130)
    d.add(Rect(25, 90, 400, 40, fillColor=colors.HexColor('#fce4d6'), strokeColor=colors.HexColor('#c65911'), radius=4))
    d.add(String(225, 105, "Data & Integrity (SQLite WAL, SHA-256 Hashes, Evidentiary PDF)", fontSize=11, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.black))

    # Reverse arrows for Cameras feeding up
    # Instead of arrow down, let's just make lines, or arrow UP from Cameras to Processing
    d.add(Line(225, 90, 225, 50, strokeWidth=2, strokeColor=colors.grey))
    
    # 5. Edge Layer (y=10 to 50)
    d.add(Rect(25, 10, 400, 40, fillColor=colors.HexColor('#e2efda'), strokeColor=colors.HexColor('#548235'), radius=4))
    d.add(String(225, 25, "Edge Network (200+ CCTV Cameras via RTSP over TCP)", fontSize=12, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.black))
    
    # Draw arrow from Edge UP to Data and Processing
    d.add(Line(100, 50, 100, 170, strokeWidth=2, strokeColor=colors.HexColor('#548235')))
    d.add(Polygon([96, 164, 104, 164, 100, 170], fillColor=colors.HexColor('#548235'), strokeColor=colors.HexColor('#548235')))
    d.add(String(105, 110, "Live RTSP Video Feed", fontSize=9, fontName='Helvetica-Oblique', fillColor=colors.HexColor('#548235')))
    
    return d

def build_hld_pdf():
    doc = SimpleDocTemplate('SentinelShield_HLD_Architecture.pdf', pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    story = []
    
    # Cover Page
    story.append(Spacer(1, 2.5*inch))
    story.append(Paragraph('Sentinel-X Gujarat Command Desk', title_style))
    story.append(Paragraph('High Level Design & System Architecture', subtitle_style))
    story.append(Spacer(1, 3.5*inch))
    story.append(Paragraph('<b>Project Documentation</b><br/>Confidential & Proprietary', ParagraphStyle('c', parent=normal, alignment=1)))
    story.append(PageBreak())
    
    # Section 1
    story.append(Paragraph('1. Executive Summary', h1))
    story.append(Paragraph('SentinelShield is an advanced modular domain subsystem designed for high-density streaming (200+ concurrent feeds) across the Gujarat CCTV network. It seamlessly integrates real-time MJPEG video multiplexing, deep learning AI inference (YOLOv8 + PaddleOCR), spatial predictive analytics, and cryptographic forensic evidence packaging into a single, cohesive ecosystem.', normal))
    
    # Section 2 - Architecture Diagram
    story.append(Paragraph('2. High-Level Architecture Block Diagram', h1))
    story.append(Paragraph('The system utilizes a 5-tier architecture to securely bridge the raw Edge RTSP network with the final operator dashboard while persisting evidentiary chains in SQLite WAL.', normal))
    story.append(Spacer(1, 10))
    story.append(KeepTogether([draw_architecture_diagram()]))
    story.append(Spacer(1, 15))
    
    # Section 3
    story.append(Paragraph('3. Subsystem Specifications', h1))
    story.append(Paragraph('<b>Frontend Client:</b>', h2))
    story.append(Paragraph('Developed in pure vanilla JavaScript using modular controllers and HTML5. Bypasses traditional iframe loading for direct API polling.', bullet))
    story.append(Paragraph('<b>Streaming Engine:</b>', h2))
    story.append(Paragraph('Engineered on OpenCV + FFmpeg, pulling direct from RTSP over TCP. Features a Multi-Process Stream Multiplexing pool with exponential backoff.', bullet))
    story.append(Paragraph('<b>Database Layer:</b>', h2))
    story.append(Paragraph('SQLite running strictly in WAL mode (<i>PRAGMA journal_mode=WAL; busy_timeout=10000</i>) ensuring zero-lock concurrency.', bullet))
    
    story.append(PageBreak())
    
    # Section 4
    story.append(Paragraph('4. Domain Subsystem Isolation Map', h1))
    data = [
        ['Module Name', 'Core Responsibilities'],
        ['core', 'Database WAL daemon, thread-safe state managers, auth.'],
        ['vision', 'Vehicle detection, CLAHE deblurring, Fast-ALPR neural engine.'],
        ['streaming', 'RTSP/MJPEG ingestion, HW-accel fallback, dynamic stream buffers.'],
        ['evidence', 'Forensic custody sealing, Section 65B courtroom brief generation.'],
        ['integrity', 'SHA-256 rolling hash chains, zero-allocation tamper checks.'],
        ['registry', 'Gujarat CCTV estate catalog and spatial resolution boundaries.']
    ]
    t = Table(data, colWidths=[120, 320])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f497d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f2f2f2')),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.HexColor('#ffffff')])
    ]))
    story.append(t)
    
    doc.build(story)
    print('Generated HLD PDF.')

def build_workflow_pdf():
    doc = SimpleDocTemplate('SentinelShield_Workflow_Integration.pdf', pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    story = []
    
    # Cover Page
    story.append(Spacer(1, 2.5*inch))
    story.append(Paragraph('Sentinel-X Gujarat Command Desk', title_style))
    story.append(Paragraph('Workflow & Integration Diagram', subtitle_style))
    story.append(Spacer(1, 3.5*inch))
    story.append(Paragraph('<b>Project Documentation</b><br/>Confidential & Proprietary', ParagraphStyle('c', parent=normal, alignment=1)))
    story.append(PageBreak())
    
    # Diagram Section
    story.append(Paragraph('1. Video Ingestion & AI Processing Workflow', h1))
    story.append(Paragraph('The following architectural diagram illustrates the lifecycle of a video frame, from the edge cameras to the operator dashboard.', normal))
    story.append(Spacer(1, 15))
    
    # DRAWING
    d = Drawing(400, 380)
    
    box_w = 260
    box_h = 40
    start_x = 120
    start_y = 330
    gap = 60
    
    # 1
    d.add(Rect(start_x, start_y, box_w, box_h, fillColor=colors.HexColor('#d9e1f2'), strokeColor=colors.HexColor('#2f5496'), radius=6))
    d.add(String(start_x + box_w/2, start_y + 14, "1. Camera Grid (RTSP over TCP)", fontSize=12, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.HexColor('#000000')))
    for s in create_arrow(start_x + box_w/2, start_y, gap - box_h): d.add(s)
    
    # 2
    start_y -= gap
    d.add(Rect(start_x, start_y, box_w, box_h, fillColor=colors.HexColor('#e2efda'), strokeColor=colors.HexColor('#548235'), radius=6))
    d.add(String(start_x + box_w/2, start_y + 14, "2. FFmpeg / MJPEG Ingestion Node", fontSize=12, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.HexColor('#000000')))
    for s in create_arrow(start_x + box_w/2, start_y, gap - box_h): d.add(s)
    
    # 3
    start_y -= gap
    d.add(Rect(start_x, start_y, box_w, box_h, fillColor=colors.HexColor('#fff2cc'), strokeColor=colors.HexColor('#bf8f00'), radius=6))
    d.add(String(start_x + box_w/2, start_y + 14, "3. AI Vision (YOLOv8 + Fast-ALPR)", fontSize=12, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.HexColor('#000000')))
    for s in create_arrow(start_x + box_w/2, start_y, gap - box_h): d.add(s)
    
    # 4
    start_y -= gap
    d.add(Rect(start_x, start_y, box_w, box_h, fillColor=colors.HexColor('#fce4d6'), strokeColor=colors.HexColor('#c65911'), radius=6))
    d.add(String(start_x + box_w/2, start_y + 14, "4. State Tracking & SQLite WAL", fontSize=12, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.HexColor('#000000')))
    for s in create_arrow(start_x + box_w/2, start_y, gap - box_h): d.add(s)
    
    # 5
    start_y -= gap
    d.add(Rect(start_x, start_y, box_w, box_h, fillColor=colors.HexColor('#e8d1ff'), strokeColor=colors.HexColor('#7030a0'), radius=6))
    d.add(String(start_x + box_w/2, start_y + 14, "5. FastAPI & Frontend Dashboard", fontSize=12, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.HexColor('#000000')))
    
    story.append(KeepTogether([d]))
    story.append(Spacer(1, 15))
    
    # Section 2
    story.append(Paragraph('2. Forensic Evidence Custody Pipeline', h1))
    story.append(Paragraph('To adhere to BSA 2023 / Section 65B courtroom requirements, the workflow forces all positive threat detections through a strict cryptographic pipeline:', normal))
    story.append(Paragraph('<b>- LSB Watermarking:</b> Video frames are injected with encrypted temporal watermarks at the pixel level.', bullet))
    story.append(Paragraph('<b>- JSON Hashing:</b> Incident metadata is serialized to a canonical JSON string and rolled into a SHA-256 chain.', bullet))
    story.append(Paragraph('<b>- Courtroom PDF Export:</b> Final incident reports encapsulate these hashes and marked images for direct judicial validation.', bullet))
    
    # Section 3
    story.append(Paragraph('3. API Integration Protocol', h1))
    data = [
        ['Integration Action', 'Endpoint', 'Protocol / Format'],
        ['Live View Init', 'POST /api/live/start', 'REST (JSON)'],
        ['Stream Feed', 'GET /api/live/stream', 'MJPEG / HTTP'],
        ['Auth Check', 'GET /api/me', 'Bearer Token'],
        ['Dashboard Telemetry', 'GET /api/overview', 'REST (JSON)']
    ]
    t = Table(data, colWidths=[140, 160, 140])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2f5496')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f9f9f9'), colors.HexColor('#ffffff')])
    ]))
    story.append(t)
    
    doc.build(story)
    print('Generated Workflow PDF.')

build_hld_pdf()
build_workflow_pdf()
