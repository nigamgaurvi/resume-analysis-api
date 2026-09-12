from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from pypdf import PdfReader
from docx import Document
import io
import re


def clean_text(text):
    text = text.replace("\n", " ")
    text = " ".join(text.split())
    return text


SKILLS = [
    "python",
    "java",
    "c++",
    "c",
    "sql",
    "mysql",
    "postgresql",
    "mongodb",
    "html",
    "css",
    "javascript",
    "fastapi",
    "flask",
    "django",
    "machine learning",
    "deep learning",
    "pandas",
    "numpy",
    "power bi",
    "excel",
    "git",
    "github",
    "docker"
]


def detect_skills(text):
    text = text.lower()

    found_skills = []

    for skill in SKILLS:
        pattern = r"\b" + re.escape(skill) + r"\b"

        if re.search(pattern, text):
            found_skills.append(skill)

    return found_skills


def detect_sections(text):
    text_lower = text.lower()

    sections = {
        "education": False,
        "skills": False,
        "experience": False,
        "projects": False,
        "certifications": False,
        "achievements": False
    }

    if "education" in text_lower:
        sections["education"] = True

    if "skills" in text_lower or "technical skills" in text_lower:
        sections["skills"] = True

    if "experience" in text_lower or "work experience" in text_lower:
        sections["experience"] = True

    if "projects" in text_lower or "academic projects" in text_lower:
        sections["projects"] = True

    if "certifications" in text_lower or "certificates" in text_lower:
        sections["certifications"] = True

    if "achievements" in text_lower or "accomplishments" in text_lower:
        sections["achievements"] = True

    return sections


def compare_skills(resume_skills, job_description):
    job_skills = detect_skills(job_description)

    matched_skills = []

    for skill in resume_skills:
        if skill in job_skills:
            matched_skills.append(skill)

    missing_skills = []

    for skill in job_skills:
        if skill not in resume_skills:
            missing_skills.append(skill)

    return matched_skills, missing_skills


def calculate_match_percentage(matched_skills, job_description):
    job_skills = detect_skills(job_description)

    if len(job_skills) == 0:
        return 0

    percentage = (len(matched_skills) / len(job_skills)) * 100

    return round(percentage, 2)


def generate_suggestions(missing_skills):

    suggestions = []

    for skill in missing_skills:
        suggestions.append(
            f"Consider adding {skill} to your resume if you have relevant experience."
        )

    if len(missing_skills) == 0:
        suggestions.append(
            "Your resume covers all the detected skills required by the job description."
        )

    return suggestions


# ---------------------------------------------------------------------------
# ATS SCORE CALCULATION
#
# The ATS Compatibility Score is out of 100 and is split into 6 transparent,
# rule-based components. Nothing here is "AI generated" — every point comes
# from a specific, explainable check on the resume text. Two components
# (keyword match and job description match) both build on the same
# skill-matching data you already had, just weighted differently:
# keyword match rewards covering the job's specific required skills, while
# job description match reuses the overall match_percentage as a broader
# compatibility signal.
# ---------------------------------------------------------------------------

def detect_contact_info(text):
    """Look for basic contact details. Only booleans are returned/used —
    we never need to store or display the actual email/phone value for
    scoring purposes."""

    email_found = bool(re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text))

    phone_found = bool(re.search(r"(\+?\d{1,3}[-.\s]?)?(\(?\d{3,4}\)?[-.\s]?)\d{3}[-.\s]?\d{3,4}", text))

    linkedin_found = "linkedin.com" in text.lower() or "linkedin" in text.lower()

    github_found = "github.com" in text.lower() or "github" in text.lower()

    return {
        "email": email_found,
        "phone": phone_found,
        "linkedin": linkedin_found,
        "github": github_found
    }


def calculate_keyword_score(matched_skills, job_description):
    """40 points: how much of the job's specific required skills are
    covered by the resume."""

    job_skills = detect_skills(job_description)

    if len(job_skills) == 0:
        # No skills detected in the JD at all, so fall back to rewarding
        # the resume for having any recognizable skills of its own.
        return 20 if len(matched_skills) >= 0 and len(matched_skills) > 0 else 10

    coverage = len(matched_skills) / len(job_skills)

    score = coverage * 40

    return round(min(score, 40), 2)


def calculate_jd_match_score(match_percentage):
    """20 points: reuses the existing overall match_percentage figure."""

    score = (match_percentage / 100) * 20

    return round(min(score, 20), 2)


def calculate_structure_score(sections):
    """15 points: 2.5 points per resume section that was detected."""

    points_per_section = 15 / len(sections)

    found_count = sum(1 for present in sections.values() if present)

    score = found_count * points_per_section

    return round(score, 2)


def calculate_contact_score(contact_info):
    """10 points: email (3), phone (3), LinkedIn (2), GitHub (2)."""

    score = 0

    if contact_info["email"]:
        score += 3

    if contact_info["phone"]:
        score += 3

    if contact_info["linkedin"]:
        score += 2

    if contact_info["github"]:
        score += 2

    return score


def calculate_formatting_score(text):
    """10 points: basic, honest checks on how cleanly the text extracted.
    This does NOT attempt to detect tables, columns, icons, or graphics —
    that isn't something this extraction method can reliably determine."""

    score = 0
    word_count = len(text.split())

    # 1. Text actually extracted and isn't essentially empty (3 pts)
    if word_count >= 30:
        score += 3

    # 2. Reasonable length, not a near-empty or clearly truncated file (3 pts)
    if word_count >= 150:
        score += 3

    # 3. Not full of unusual/garbled characters from a bad extraction (2 pts)
    if len(text) > 0:
        alnum_count = sum(1 for ch in text if ch.isalnum() or ch.isspace())
        clean_ratio = alnum_count / len(text)

        if clean_ratio >= 0.85:
            score += 2

    # 4. Not excessively repetitive text (2 pts)
    words = text.lower().split()

    if len(words) > 0:
        unique_ratio = len(set(words)) / len(words)

        if unique_ratio >= 0.3:
            score += 2

    return score


def calculate_content_score(text):
    """5 points: a small score for having a reasonable amount of content."""

    word_count = len(text.split())

    if word_count >= 400:
        return 5
    elif word_count >= 250:
        return 4
    elif word_count >= 150:
        return 3
    elif word_count >= 80:
        return 2
    elif word_count > 0:
        return 1
    else:
        return 0


def calculate_ats_score(text, matched_skills, job_description, sections):
    """Combines every component into the final ATS Compatibility Score."""

    match_percentage = calculate_match_percentage(matched_skills, job_description)
    contact_info = detect_contact_info(text)

    keyword_match = calculate_keyword_score(matched_skills, job_description)
    job_description_match = calculate_jd_match_score(match_percentage)
    resume_structure = calculate_structure_score(sections)
    contact_information = calculate_contact_score(contact_info)
    ats_formatting = calculate_formatting_score(text)
    content_quality = calculate_content_score(text)

    total = (
        keyword_match
        + job_description_match
        + resume_structure
        + contact_information
        + ats_formatting
        + content_quality
    )

    breakdown = {
        "keyword_match": keyword_match,
        "job_description_match": job_description_match,
        "resume_structure": resume_structure,
        "contact_information": contact_information,
        "ats_formatting": ats_formatting,
        "content_quality": content_quality
    }

    return round(total, 2), breakdown, contact_info


def generate_insights(sections, contact_info, matched_skills, missing_skills, match_percentage):
    """Simple, explainable observations built directly from the analysis —
    nothing here is invented or randomized."""

    insights = []

    if len(matched_skills) >= 5:
        insights.append({"type": "positive", "text": "Strong technical skill coverage"})
    elif len(matched_skills) > 0:
        insights.append({"type": "positive", "text": "Some relevant skills detected"})

    if match_percentage >= 60:
        insights.append({"type": "positive", "text": "Good job-description alignment"})
    elif match_percentage < 40:
        insights.append({"type": "warning", "text": "Low alignment with the job description"})

    if len(missing_skills) > 0:
        insights.append({"type": "warning", "text": "Missing important keywords from the job description"})

    if not contact_info["linkedin"]:
        insights.append({"type": "warning", "text": "LinkedIn profile not detected"})

    if not contact_info["email"]:
        insights.append({"type": "warning", "text": "Email address not detected"})

    missing_sections = [name for name, present in sections.items() if not present]

    if missing_sections:
        insights.append({
            "type": "warning",
            "text": f"Missing section(s): {', '.join(missing_sections)}"
        })

    return insights


app = FastAPI()

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@app.get("/", response_class=HTMLResponse)
def home():
    with open("templates/index.html", "r") as file:
        return file.read()


@app.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    job_description: str = Form(...)
):

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE_BYTES:
        return {
            "error": "File is too large. Please upload a resume under 5MB."
        }

    if file.filename.endswith(".pdf"):

        pdf_file = io.BytesIO(contents)
        reader = PdfReader(pdf_file)

        text = ""

        for page in reader.pages:
            text += page.extract_text() or ""

    elif file.filename.endswith(".docx"):

        docx_file = io.BytesIO(contents)
        document = Document(docx_file)

        text = ""

        for paragraph in document.paragraphs:
            text += paragraph.text + "\n"

    else:

        return {
            "error": "Only PDF and DOCX files are supported."
        }

    cleaned_text = clean_text(text)

    skills = detect_skills(cleaned_text)
    sections = detect_sections(cleaned_text)

    matched_skills, missing_skills = compare_skills(skills, job_description)
    match_percentage = calculate_match_percentage(matched_skills,job_description)
    suggestions = generate_suggestions(missing_skills)

    ats_score, ats_breakdown, contact_info = calculate_ats_score(
        cleaned_text, matched_skills, job_description, sections
    )

    insights = generate_insights(
        sections, contact_info, matched_skills, missing_skills, match_percentage
    )

    return {
    "filename": file.filename,
    "text": cleaned_text,
    "skills": skills,
    "job_description": job_description,
    "matched_skills": matched_skills,
    "missing_skills": missing_skills,
    "match_percentage": match_percentage,
    "suggestions": suggestions,
    "sections": sections,
    "contact_info": contact_info,
    "ats_score": ats_score,
    "ats_breakdown": ats_breakdown,
    "insights": insights
}