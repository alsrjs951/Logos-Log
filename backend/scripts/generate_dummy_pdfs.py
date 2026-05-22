import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/raw'))

def create_pdf(filename, title, content):
    filepath = os.path.join(RAW_DIR, filename)
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 72, title)
    
    # Content
    c.setFont("Helvetica", 12)
    y_position = height - 100
    
    for line in content.split('\n'):
        if y_position < 72:
            c.showPage()
            c.setFont("Helvetica", 12)
            y_position = height - 72
        c.drawString(72, y_position, line)
        y_position -= 15
        
    c.save()
    print(f"Created: {filepath}")

def main():
    if not os.path.exists(RAW_DIR):
        os.makedirs(RAW_DIR)
        
    doc1 = {
        "filename": "logotherapy_frankl_1946_dummy.pdf",
        "title": "Man's Search for Meaning: An Introduction to Logotherapy",
        "content": """
Logotherapy is a therapeutic approach that helps people find personal 
meaning in life. It's a form of psychotherapy that is focused on the future 
and on our ability to endure hardship and suffering through a search for purpose.

1. The Will to Meaning
The primary motivational force of an individual is to find a meaning in life.
Unlike Freud's will to pleasure or Adler's will to power, Frankl believed 
that humans are driven by a "will to meaning."

2. Meaning in Suffering
When we are no longer able to change a situation, we are challenged to change 
ourselves. Suffering ceases to be suffering at the moment it finds a meaning, 
such as the meaning of a sacrifice.

3. The Existential Vacuum
A widespread phenomenon of the twentieth century, the existential vacuum is 
the feeling of total and ultimate meaninglessness of one's life. It often 
manifests as a state of boredom.
"""
    }

    doc2 = {
        "filename": "positive_psych_seligman_2011_dummy.pdf",
        "title": "Flourish: A Visionary New Understanding of Happiness and Well-being",
        "content": """
Positive Psychology focuses on what makes life worth living. It shifts the 
focus from repairing the worst things in life to building the best qualities 
in life.

The PERMA Model:
P - Positive Emotion: Experiencing joy, hope, and gratitude.
E - Engagement: Being fully absorbed in activities (flow).
R - Relationships: Having authentic, life-enhancing connections.
M - Meaning: Belonging to and serving something bigger than the self.
A - Accomplishment: Pursuing success, winning, achievement, and mastery.

By cultivating these five elements, individuals can achieve a state of 
flourishing, moving beyond mere survival or absence of mental illness.
"""
    }

    create_pdf(doc1["filename"], doc1["title"], doc1["content"])
    create_pdf(doc2["filename"], doc2["title"], doc2["content"])

if __name__ == '__main__':
    main()
