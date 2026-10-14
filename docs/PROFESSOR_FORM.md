# Professor survey: paste into Google Forms or Microsoft Forms

This is the instructor survey. The website reads its exported responses, so a few setup rules matter.

## Setup rules (important)

1. **Keep the `Q1.` … `Q10.` numbers at the start of every question title.** The website finds each answer by that number. You can reword the rest of a question freely.
2. **Use "Multiple choice" for Q5–Q8**, not "Linear scale". Linear scale only labels the two ends; multiple choice lets professors see every option. Keep each option starting with its number (`1 — …`).
3. Mark Q1, Q2, Q3, Q5, Q6, Q7, Q8 and Q10 as **required**.
4. Turn **off** email collection unless you need it. The website ignores email columns anyway.
5. Ask professors who teach several courses to submit **once per course**.

---

## Form title

Prof-Match pilot: how your course runs

## Form description

> Prof-Match is a student project for the Marist Innovation Challenge. It is not an official Marist service. It helps students compare sections of the same course based on how classes are run, so they know what to expect before registering.
>
> Your answers describe how your course is organized, not teaching quality. No answer is better than another. If you agree in the last question, students using the pilot will see your name and these answers, labeled as self-reported by you.
>
> You can ask for corrections or removal at any time: [YOUR EMAIL]. Responses are kept until December 7, 2026 unless you agree to longer. It takes about 2 minutes.

---

## Questions

**Q1. Your name as you'd like students to see it (e.g., Dr. Jane Smith)**
Short answer · required

**Q2. Course code (e.g., MATH 130)**
Short answer · required
Help text: If you teach more than one course, please submit this form once per course.

**Q3. Term these answers apply to (e.g., Spring 2027)**
Short answer · required

**Q4. Section number(s), if known (e.g., 111, 112)**
Short answer · optional

**Q5. In this course, how is class time mostly spent?**
Multiple choice · required
- 1 — Mostly lecture
- 2 — Between mostly lecture and roughly balanced
- 3 — Roughly balanced
- 4 — Between roughly balanced and mostly discussion/interactive activities
- 5 — Mostly discussion/interactive activities
- Not sure / it varies

**Q6. How is graded work distributed?**
Multiple choice · required
- 1 — A few major assessments
- 2 — Between a few major assessments and a mixture
- 3 — A mixture
- 4 — Between a mixture and frequent smaller assessments
- 5 — Frequent smaller assessments
- Not sure / it varies

**Q7. Are assessed assignments mostly individual or group work?**
Multiple choice · required
- 1 — Mostly individual
- 2 — Between mostly individual and mixed
- 3 — Mixed
- 4 — Between mixed and mostly group work
- 5 — Mostly group work
- Not sure / it varies

**Q8. How much of the course plan is fixed in advance?**
Multiple choice · required
- 1 — Flexible, evolving plans
- 2 — Between flexible plans and some fixed structure
- 3 — Some fixed structure
- 4 — Between some fixed structure and detailed schedules in advance
- 5 — Detailed schedules/instructions in advance
- Not sure / it varies

**Q9. Anything students should know, or anything that may change next term? (shown to students)**
Paragraph · optional

**Q10. May Prof-Match show your name and these answers to students in the pilot?**
Multiple choice · required
- Yes, show my name and answers
- No, do not show my responses

---

## Getting responses into the website

**Google Forms:** Responses tab → link to Sheets → in the sheet, File → Download → Comma-separated values (.csv).

**Microsoft Forms:** Responses → Open results in Excel → File → Save As → CSV UTF-8.

Then save the file as `data/private/professor_responses.csv` inside the project folder and refresh the website. It will offer "Pilot data" alongside the synthetic demo. The `data/private/` folder is excluded from git, so responses are never committed by accident.

The website will:
- skip anyone who answered "No" to Q10;
- treat "Not sure / it varies" as unknown (never as 3);
- keep only the latest response if someone submits twice for the same course and term;
- show every skipped row and the reason under "Data status" in the sidebar.

---

## Short invitation message (edit before sending; you send it, not Claude)

> Subject: 2-minute survey for a student course-comparison project
>
> Hi Professor [Name],
>
> I'm a junior in Applied Math and Data Science working on Prof-Match, a student project for the Marist Innovation Challenge. It helps students compare sections of the same course by how classes are run (lecture vs. discussion, assessment spacing, group work, advance structure), not by ratings.
>
> Would you be willing to fill out a short form about how [COURSE] is organized? It takes about two minutes, and your answers are only shown if you agree to that in the last question.
>
> [FORM LINK]
>
> Thank you,
> Saad
