from fpdf import FPDF
import os

class OffGridManual(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(33, 37, 41)
        self.cell(0, 10, 'Off-Grid Agent: Official Command Manual', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(108, 117, 125)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def section_header(self, title):
        self.ln(5)
        self.set_font('Helvetica', 'B', 14)
        self.set_fill_color(233, 236, 239)
        self.cell(0, 10, title, 0, 1, 'L', True)
        self.ln(4)

    def add_command(self, title, syntax, example, desc, output, img=None):
        if self.get_y() > 220:
            self.add_page()
            
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(0, 123, 255)
        self.cell(0, 8, title, 0, 1)
        
        self.set_font('Courier', 'B', 10)
        self.set_text_color(52, 58, 64)
        self.cell(25, 7, ' Syntax:', 0, 0)
        self.set_font('Courier', '', 10)
        self.multi_cell(0, 7, syntax)
        
        self.set_font('Courier', 'B', 10)
        self.cell(25, 7, ' Example:', 0, 0)
        self.set_font('Courier', 'I', 10)
        self.multi_cell(0, 7, example)
        
        self.set_font('Helvetica', 'B', 10)
        self.cell(25, 7, ' Details:', 0, 0)
        self.set_font('Helvetica', '', 10)
        self.multi_cell(0, 7, desc)

        if img and os.path.exists(img):
            self.ln(2)
            if self.get_y() > 180:
                self.add_page()
            self.image(img, x=20, w=170)
            self.ln(2)

        self.set_font('Helvetica', 'B', 10)
        self.cell(25, 7, ' Output:', 0, 0)
        self.set_font('Helvetica', 'I', 10)
        self.multi_cell(0, 7, output)
        self.ln(8)

pdf = OffGridManual(orientation='P', unit='mm', format='A4')
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

# --- WEATHER & RADAR SECTION ---
pdf.section_header('1. Weather & Environmental Data')

# Radar Group
pdf.add_command(
    'Static Radar Map',
    '!radar <location> <miles>',
    '!radar Seattle 30',
    'Generates a high-quality NEXRAD composite with 60% transparency and smoothing.',
    'Weather Radar: Seattle (30 mi) | Now: 45F, Light Rain | HQ Link: tmpfiles.org/dl/12345/radar.png | (Full image attached as MMS)',
    img='doc_assets/radar_static.png'
)

pdf.add_command(
    'Animated Radar (30-Minute Loop)',
    '!radar <location> <miles> gif 30',
    '!radar Seattle 30 gif 30',
    'Generates an animated sequence of the last 30 minutes of weather data at 5-minute intervals.',
    'Radar Loop: Seattle (30 mi) | Time: Past 30m (-5m intervals) | HQ Animation: tmpfiles.org/dl/67890/radar.gif | (GIF attached as MMS)',
    img='doc_assets/radar_30m.gif' if os.path.exists('doc_assets/radar_30m.gif') else 'doc_assets/radar_static.png'
)

pdf.add_command(
    'Animated Radar (60-Minute Loop)',
    '!radar <location> <miles> gif 60',
    '!radar Seattle 30 gif 60',
    'Generates an extended 60-minute sequence to track large fronts or long-term trends.',
    'Radar Loop: Seattle (30 mi) | Time: Past 60m (-5m intervals) | HQ Animation: tmpfiles.org/dl/11223/radar_60.gif | (GIF attached as MMS)',
    img='doc_assets/radar_60m.gif' if os.path.exists('doc_assets/radar_60m.gif') else 'doc_assets/radar_static.png'
)

# Forecast Group
pdf.add_command(
    'General Forecast',
    '!forecast <location>',
    '!forecast Seattle',
    'Fetches a standard 12-hour hourly breakdown (temperature and general conditions).',
    'Forecast for Seattle (12h): Now: 42F (Cloudy) | 8am: 42F (Cloudy) | 9am: 43F (Rain) | 10am: 41F (Storms) | 11am: 40F (Storms) | 12pm: 39F (Rain) | 1pm: 38F (Cloudy) | 2pm: 38F (Cloudy) | 3pm: 39F (Cloudy) | 4pm: 39F (Cloudy) | 5pm: 38F (Cloudy) | 6pm: 37F (Cloudy) | 7pm: 36F (Cloudy)'
)

pdf.add_command(
    'Targeted Forecast: Temperature',
    '!forecast(temp)(<hrs>) <location>',
    '!forecast(temp)(24) Seattle',
    'Filters the forecast to show only temperature trends for the requested duration.',
    'Temp Trend: Seattle | 8am: 42F | 9am: 41F | 10am: 40F | 11am: 39F | 12pm: 40F | 1pm: 42F | 2pm: 43F | 3pm: 44F | 4pm: 44F | 5pm: 43F | 6pm: 41F | 7pm: 39F | 8pm: 37F | 9pm: 36F | 10pm: 35F | 11pm: 34F | 12am: 33F | 1am: 32F | 2am: 32F | 3am: 31F | 4am: 31F | 5am: 32F | 6am: 33F | 7am: 35F'
)

pdf.add_command(
    'Targeted Forecast: Wind',
    '!forecast(wind)(<hrs>) <location>',
    '!forecast(wind)(12) Seattle',
    'Filters the forecast to show wind speed and direction trends.',
    'Wind Forecast: Seattle | 8am: 10mph SW | 9am: 12mph W | 10am: 15mph NW | 11am: 14mph NW | 12pm: 12mph N | 1pm: 10mph N | 2pm: 8mph NE | 3pm: 5mph E | 4pm: 5mph SE | 5pm: 8mph S | 6pm: 10mph SW | 7pm: 12mph SW'
)

pdf.add_command(
    'Targeted Forecast: Conditions',
    '!forecast(cond)(<hrs>) <location>',
    '!forecast(cond)(48) Seattle',
    'Filters the forecast to show only weather states (Sunny, Rain, Snow, etc).',
    'Conditions: Seattle | 8am: Clear | 12pm: P.Cloudy | 4pm: Rain | 8pm: Storms | 12am: Rain | 4am: Cloudy | 8am: Clear | 12pm: Clear | 4pm: P.Cloudy | 8pm: Clear | 12am: Fog | 4am: Fog'
)

pdf.add_command(
    'Targeted Forecast: Precipitation',
    '!forecast(precip)(<hrs>) <location>',
    '!forecast(precip)(12) Seattle',
    'Filters the forecast to show specific rain/snow probability and accumulation.',
    'Precipitation: Seattle | 8am: 10% (0in) | 9am: 80% (0.2in) | 10am: 100% (0.5in) | 11am: 100% (0.4in) | 12pm: 90% (0.2in) | 1pm: 60% (0.1in) | 2pm: 40% (0.05in) | 3pm: 20% (0in) | 4pm: 10% (0in) | 5pm: 0% (0in) | 6pm: 0% (0in) | 7pm: 0% (0in)'
)

pdf.add_command(
    'Temperature History',
    '!temp-history <location>',
    '!temp-history Seattle',
    'Provides the actual observed temperatures from the past 24 hours.',
    'Observation Trend (Past 24h): 4am: 37F | 5am: 37F | 6am: 39F | 7am: 40F | 8am: 42F | 9am: 43F | 10am: 45F | 11am: 46F | 12pm: 47F | 1pm: 48F | 2pm: 49F | 3pm: 50F | 4pm: 50F | 5pm: 49F | 6pm: 47F | 7pm: 45F | 8pm: 43F | 9pm: 42F | 10pm: 41F | 11pm: 40F | 12am: 39F | 1am: 38F | 2am: 38F | 3am: 38F'
)

# --- RESEARCH & KNOWLEDGE ---
pdf.section_header('2. Research & Knowledge')

pdf.add_command(
    'Wikipedia Search',
    '!wiki <query>',
    '!wiki Nikola Tesla',
    'Direct lookup in the offline Wikipedia (ZIM) archive. Fast and works without internet.',
    'Nikola Tesla (1856-1943) was a Serbian-American inventor, electrical engineer, and mechanical engineer best known for his contributions to the design of the modern alternating current (AC) electricity supply system...'
)

pdf.add_command(
    'Deep Research',
    '!research <topic>',
    '!research How to build a solar kiln',
    'Autonomous multi-step investigation using Web, Maps, and Wikipedia. Generates a full PDF report.',
    'Starting Deep Research on "How to build a solar kiln"... (Agent will text you a link to the PDF report when complete)'
)

pdf.add_command(
    'Identify (Plant/Object)',
    '!identify',
    '!identify (sent with image)',
    'Specialized identification for plants, leaves, and objects. Triggered automatically by image attachments.',
    'Identified: American White Oak (Quercus alba) (98.2% confidence). Found in the center of image.'
)

# --- UTILITIES ---
pdf.section_header('3. Specialized Utilities')

pdf.add_command(
    'System Health',
    '!check',
    '!check',
    'Diagnostic report for connectivity and hardware status.',
    'SYSTEM STATUS: [OK] Gmail Connection | [OK] AI Backend (LM Studio) | [OK] Disk (42% free) | [OK] Database Online | Load Average: 0.15, 0.22, 0.28'
)

# --- MANAGEMENT ---
pdf.section_header('4. Agent Management')

pdf.add_command(
    'Clear History',
    '!clear',
    '!clear',
    'Wipes your personal thread history from the agent database.',
    '[OK] History cleared. Removed 42 conversations from database for your number.'
)

pdf.add_command(
    'Command List',
    '!info',
    '!info',
    'Displays the internal help reference list.',
    'OFF-GRID AGENT - COMMAND LIST | --- WEATHER --- | !weather <loc> | !radar <loc> <miles> gif 30 | !radar <loc> <miles> (static) | !forecast <loc> | --- UTILITIES --- | !check | !clear | !test | !info | [ FULL MANUAL PDF ] tmpfiles.org/dl/manual.pdf'
)

output_file = os.path.join(os.path.dirname(__file__), "..", "Off-Grid_Agent_Manual_Full.pdf")
pdf.output(output_file)
print(f"Created {output_file}")
