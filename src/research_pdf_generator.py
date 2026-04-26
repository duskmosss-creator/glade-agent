from fpdf import FPDF
import os
import datetime

class ResearchReportPDF(FPDF):
    def __init__(self, title="Research Report", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = title
        
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(33, 37, 41)
        self.cell(0, 10, self.report_title, 0, 1, 'C')
        self.ln(5)
        # Add timestamp
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(100, 100, 100)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cell(0, 5, f"Generated: {timestamp}", 0, 1, 'R')
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(108, 117, 125)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, label):
        self.ln(4)
        self.set_font('Helvetica', 'B', 14)
        self.set_fill_color(233, 236, 239)
        self.set_text_color(0, 0, 0)
        self.cell(0, 8, label, 0, 1, 'L', True)
        self.ln(2)

    def body_text(self, text):
        self.set_font('Helvetica', '', 11)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def source_link(self, title, url):
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(0, 0, 255)
        self.cell(0, 6, f"{chr(149)} {title}", link=url, ln=1)
        self.set_text_color(0, 0, 0)

def generate_research_report(filename, title, summary, sections, sources=[]):
    """
    Generates a PDF report.
    :param filename: Output path.
    :param title: Report title.
    :param summary: Executive summary text.
    :param sections: List of dicts {'title': str, 'content': str}.
    :param sources: List of dicts {'title': str, 'url': str}.
    """
    pdf = ResearchReportPDF(title=title)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Summary
    pdf.chapter_title("Executive Summary")
    pdf.body_text(summary)
    pdf.ln(5)
    
    # Sections
    for section in sections:
        pdf.chapter_title(section.get('title', 'Untitled Section'))
        pdf.body_text(section.get('content', ''))
        
    # Sources
    if sources:
        pdf.add_page()
        pdf.chapter_title("Sources & References")
        for source in sources:
            pdf.source_link(source.get('title', 'Source'), source.get('url', ''))
            
    pdf.output(filename)
    return filename

if __name__ == "__main__":
    # Test
    secs = [
        {'title': 'Introduction', 'content': 'This is the intro.'},
        {'title': 'Deep Dive', 'content': 'Detailed analysis goes here. ' * 50}
    ]
    srcs = [
        {'title': 'Google', 'url': 'https://google.com'},
        {'title': 'DuckDuckGo', 'url': 'https://duckduckgo.com'}
    ]
    generate_research_report("test_report.pdf", "Test Research Report", "This is a summary of the findings.", secs, srcs)
    print("Report generated.")
