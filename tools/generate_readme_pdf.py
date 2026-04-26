from fpdf import FPDF
import os

class ReadmePDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(33, 37, 41)
        self.cell(0, 10, 'Off-Grid SMS Agent: README', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(108, 117, 125)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, label):
        self.ln(2)
        self.set_font('Helvetica', 'B', 14)
        self.set_fill_color(233, 236, 239)
        self.cell(0, 8, label, 0, 1, 'L', True)
        self.ln(2)

    def chapter_subtitle(self, label):
        self.ln(1)
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6, label, 0, 1)
        self.ln(0)

    def body_text(self, text):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 5, text)

    def bullet_point(self, text, indent=0):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(50, 50, 50)
        self.set_x(15 + indent)
        self.multi_cell(0, 6, f"{chr(149)} {text}")

    def code_block(self, code_lines):
        self.set_font('Courier', '', 9)
        self.set_text_color(0, 0, 0)
        self.set_fill_color(245, 245, 245)
        full_text = "\n".join(code_lines)
        self.multi_cell(0, 5, full_text, 0, 'L', True)
        self.ln(2)

    def render_table(self, header, rows):
        # Column widths
        self.set_font('Helvetica', 'B', 10)
        w = [25, 60, 100] # Command, Syntax, Description
        
        # Header
        for i, h in enumerate(header):
            self.cell(w[i], 7, h, 1, 0, 'C', True)
        self.ln()
        
        # Data
        self.set_font('Helvetica', '', 10)
        for row in rows:
            max_lines = 1
            # Calculate max height needed
            for i, data in enumerate(row):
                # Rough estimate of lines needed
                lines = len(data) // 40 # approx characters
                if lines > max_lines: max_lines = lines + 1
            
            h = 6 * max_lines
            
            self.cell(w[0], h, row[0], 1)
            
            x = self.get_x()
            y = self.get_y()
            self.multi_cell(w[1], 6, row[1], 1)
            self.set_xy(x + w[1], y)
            
            self.multi_cell(w[2], 6, row[2], 1)
           # self.ln()

def generate_pdf(txt_path, pdf_path):
    pdf = ReadmePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    in_code_block = False
    code_buffer = []
    in_table = False
    table_header = []
    table_rows = []
    
    for line in lines:
        line = line.rstrip()
        # Sanitize common unicode chars that break standard FPDF
        line = line.replace('\u2014', '--').replace('\u2013', '-').replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
        # Strip all other non-latin1 characters (like emojis)
        line = line.encode('latin-1', 'ignore').decode('latin-1')
        
        # Handle Code Blocks
        if line.strip().startswith("```"):
            if in_code_block:
                # End block
                pdf.code_block(code_buffer)
                code_buffer = []
                in_code_block = False
            else:
                # Start block
                in_code_block = True
            continue
            
        if in_code_block:
            code_buffer.append(line)
            continue
            
        # Handle Table
        if "|" in line and "-+-" not in line and "---" not in line and not line.startswith("---"):
            if not in_table:
                # Assuming first row is header if we just started
                # But headers usually separate by ---
                pass
            
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p] # Remove empty start/end
            
            if len(parts) >= 3:
                # Check if it's a separator line
                if set(parts[0]) == {'-'}: 
                    # End of header, start of body (conceptually)
                    # We can instruct render to treat first row as header if we buffered it
                    pass
                elif "Command" in parts[0]:
                    in_table = True
                    table_header = parts
                else:
                    if in_table:
                        table_rows.append(parts)
            continue

        if in_table and ("|" not in line or not line.strip()):
            # Table ended
            # Render simple list fallback for now if complex, or just dump it
            # Simplified for this specific README table structure:
            pdf.ln(2)
            pdf.set_font('Courier', '', 9)
            if table_header:
                 pdf.cell(30, 6, "COMMAND", 1)
                 pdf.cell(50, 6, "SYNTAX", 1)
                 pdf.cell(0, 6, "DESCRIPTION", 1)
                 pdf.ln()
            for row in table_rows:
                 if len(row) >= 3:
                    pdf.cell(30, 6, row[0], 1)
                    pdf.cell(50, 6, row[1], 1)
                    pdf.cell(0, 6, row[2], 1)
                    pdf.ln()
            pdf.ln(5)
            in_table = False
            table_header = []
            table_rows = []
        
        # Markdown Headers
        if line.startswith("## "):
            if in_table: in_table=False # Force close table
            pdf.chapter_title(line.replace("## ", "").strip())
        elif line.startswith("### "):
            pdf.chapter_subtitle(line.replace("### ", "").strip())
        elif line.startswith("=") and len(line) > 3:
            # Title underline
            pass 
        elif line.strip() == "---":
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
        # Bullet Points
        elif line.strip().startswith("- ") or line.strip().startswith("* "):
            indent = 0
            if line.startswith("    "): indent = 10
            pdf.bullet_point(line.strip()[2:], indent)
        # Numbered Lists
        elif len(line) > 2 and line[0].isdigit() and line[1] == ".":
             pdf.bullet_point(line, 0)
        # Normal Text
        else:
            if line.strip():
                pdf.body_text(line)
            else:
                 pdf.ln(2)

    pdf.output(pdf_path)
    print(f"Generated {pdf_path}")

if __name__ == "__main__":
    generate_pdf(os.path.join(os.path.dirname(__file__), "..", "README.md"), 
                os.path.join(os.path.dirname(__file__), "..", "README.pdf"))
