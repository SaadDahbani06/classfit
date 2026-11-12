# Instructor form (questionnaire v2): paste into Google Forms or Microsoft Forms

This is the instructor survey for ClassFit (working name). The website reads its exported responses, so a few setup rules matter. Version 2 replaces the four-question version 1; version-1 exports are refused rather than converted (see `src/profmatch/scale.py`).

## Setup rules (important)

1. **Keep the start of every question title exactly as written**: the number for every question (`Q1.` … `Q12.`), and the number plus topic for Q5–Q10 (for example `Q5. Class discussion — …`). The website finds each answer by that start; you can reword the rest of a question.
2. **Use "Multiple choice" for Q5–Q10**, not "Linear scale", so instructors see every labelled answer. Keep each option starting with its number (`1 — …`) and keep "Varies / unable to answer" as the last option.
3. **Make Q3 (term) a dropdown** listing the terms you are collecting, for example "Spring 2027". Free text works, but "Spring 2027" and "Spr 2027" would be treated as different terms.
4. Mark Q1, Q2, Q3, Q5–Q10 and Q12 as **required**.
5. Turn **off** email collection unless you need it. The website ignores email columns anyway.
6. Ask instructors to submit **once per course per term**. If they teach several sections of that course differently, they should choose "Varies / unable to answer" wherever the sections differ.
7. Keep "v2" in the form title so exports from different versions are easy to tell apart.

---

## Form title

ClassFit pilot (v2): how your course runs

## Form description

> ClassFit (working name) is a student project for the Marist Innovation Challenge. It is not an official Marist service. It helps students compare sections of the same course by how classes are run, so they know what to expect before registering.
>
> Please answer for **one course in one term**. Your answers describe how the course is organized, not teaching quality; no answer is better than another. If a practice differs between your sections, or you can't say, choose "Varies / unable to answer". It is never guessed.
>
> If you agree in the last question, students using the pilot will see your name and these answers, labelled as self-reported by you. Your optional note is shown to students but never affects the comparison.
>
> You can ask for corrections or removal at any time: [YOUR EMAIL]. Responses are kept until December 7, 2026 unless you agree to longer. It takes a few minutes.

---

## Questions

**Q1. Your name as students should see it (e.g., Dr. Jane Smith)**
Short answer · required

**Q2. Course code (e.g., MATH 130)**
Short answer · required
Help text: If you teach more than one course, please submit this form once per course.

**Q3. Term these answers describe (e.g., Spring 2027)**
Dropdown (recommended) or short answer · required

**Q4. Section number(s), if known (e.g., 111, 112)**
Short answer · optional

**Q5. Class discussion — In this course and term, how often do class sessions include discussion?**
Multiple choice · required
Help text: Discussion means students talking through ideas with each other or the whole class, beyond quick questions and answers.
- 1 — Rarely (0–20% of class sessions)
- 2 — Sometimes (21–40% of class sessions)
- 3 — About half (41–60% of class sessions)
- 4 — Often (61–80% of class sessions)
- 5 — Almost always (81–100% of class sessions)
- Varies / unable to answer

**Q6. Guided practice — In this course and term, how much class time is spent on guided practice?**
Multiple choice · required
Help text: Guided practice means students working on problems or tasks during class while the instructor (or a TA) helps and gives feedback.
- 1 — Little (0–20% of class time)
- 2 — Some (21–40% of class time)
- 3 — About half (41–60% of class time)
- 4 — Most (61–80% of class time)
- 5 — Nearly all (81–100% of class time)
- Varies / unable to answer

**Q7. Following the plan — In this course and term, how closely do classes follow the plan shared at the start of the term?**
Multiple choice · required
Help text: The plan is the schedule of topics, readings and due dates students receive at the start of the term.
- 1 — Set as we go (no dated schedule at the start)
- 2 — Changes often (the dated schedule changes most weeks)
- 3 — Changes sometimes (the dated schedule changes every few weeks)
- 4 — Changes rarely (the dated schedule changes once or twice a term)
- 5 — Followed closely (a detailed dated schedule, kept as published)
- Varies / unable to answer

**Q8. Concepts and applications — In this course and term, what is the balance of concepts and applications in class?**
Multiple choice · required
Help text: Concepts are ideas, theory and why things work. Applications are using those ideas on real problems, cases, data or projects.
- 1 — Mostly concepts (over 80% of class time on concepts)
- 2 — More concepts (about 60–80% on concepts)
- 3 — Even balance (about 40–60% on each)
- 4 — More applications (about 60–80% on applications)
- 5 — Mostly applications (over 80% of class time on applications)
- Varies / unable to answer

**Q9. Timed quizzes and exams — In this course and term, what share of the course grade comes from timed quizzes and exams?**
Multiple choice · required
Help text: Timed means completed within a set time limit, in class or online: quizzes, midterms and finals.
- 1 — 0–20% of the course grade
- 2 — 21–40% of the course grade
- 3 — 41–60% of the course grade
- 4 — 61–80% of the course grade
- 5 — 81–100% of the course grade
- Varies / unable to answer

**Q10. Collaborative graded work — In this course and term, what share of the course grade comes from work students complete together?**
Multiple choice · required
Help text: Work done together means graded group projects, team assignments or pair work that students are asked to complete with others.
- 1 — 0–20% of the course grade
- 2 — 21–40% of the course grade
- 3 — 41–60% of the course grade
- 4 — 61–80% of the course grade
- 5 — 81–100% of the course grade
- Varies / unable to answer

**Q11. Anything students should know? (optional; shown to students; not part of the match)**
Paragraph · optional

**Q12. May ClassFit show your name and these answers to students in the pilot?**
Multiple choice · required
- Yes, show my name and answers
- No, do not show my responses

---

## Getting responses into the website

**Google Forms:** Responses tab → link to Sheets → in the sheet, File → Download → Comma-separated values (.csv).

**Microsoft Forms:** Responses → Open results in Excel → File → Save As → CSV UTF-8. (Plain "CSV" breaks the dashes in the answers; the website will say so.)

Then save the file as `data/private/professor_responses.csv` inside the project folder and refresh the website: it shows the pilot data automatically. To see skipped rows or switch back to the synthetic demo, open the site with `?admin=1` at the end of the address (for example `http://localhost:8501/?admin=1`) and use "Technical details" in the sidebar. Students never see that section. The `data/private/` folder is excluded from git, so responses are never committed by accident.

The website will:
- skip anyone who answered "No" to Q12;
- treat "Varies / unable to answer" (or a blank answer) as unknown, never as a number;
- refuse a version-1 export, with an explanation, instead of reading it as version 2;
- keep only the latest response if someone submits twice for the same course and term;
- list every skipped or replaced row, with the reason, under "Technical details" in the sidebar (with `?admin=1`).

---

## Short invitation message (edit before sending; you send it, not Claude)

> Subject: Short survey for a student course-comparison project
>
> Hi Professor [Name],
>
> I'm a junior in Applied Math and Data Science working on ClassFit (a working name), a student project for the Marist Innovation Challenge. It helps students compare sections of the same course by how classes are run (how often there is discussion, how much guided practice, how closely the plan is followed, the balance of concepts and applications, and how much of the grade comes from timed exams and group work), not by ratings.
>
> Would you be willing to fill out a short form about how [COURSE] runs in [TERM]? It takes a few minutes, and your answers are only shown if you agree to that in the last question.
>
> [FORM LINK]
>
> Thank you,
> Saad
