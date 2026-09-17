# Business Requirements: Course Delivery & Interactive Content Blocks

**Requirement ID:** BFR-LMS-001  
**Domain:** Curriculum Delivery, Learning & Evaluation (LMS)  
**Stakeholders:** Subject Teachers, Department Heads, Instructional Designers, Students  
**Classification:** Pure Business Requirements Specification (LearnHouse Foundation Revamped)  

---

## 1. Business Need & Operational Overview

To engage modern digital-native students, an educational platform must deliver content far beyond static PDF downloads. Teachers require a modular, flexible course-authoring canvas where they can organize instructional units into structured chapters, combine multimedia formats (video, audio, rich-text, simulations, SCORM interactive modules), and lock progression behind mastery checks.

The **Course Delivery & Interactive Content Blocks** module, built upon the **LearnHouse** content architecture, governs the creation, organization, versioning, and pedagogical delivery of course materials across web and mobile interfaces.

---

## 2. Core Business Capabilities & Rules

### 2.1 The LearnHouse Content Hierarchy
Content is organized in a clean 4-tier pedagogical structure:
1. **Course:** The high-level subject course (e.g., "AP Physics 1 - Grade 11").
2. **Chapter / Unit:** The thematic curricular unit (e.g., "Chapter 3: Circular Motion & Gravitation").
3. **Activity:** The individual instructional lesson or learning event (e.g., "Lesson 3.2: Universal Law of Gravitation").
4. **Content Blocks:** The modular pedagogical components composing each activity (Rich Text, Video, Quiz, Interactive Code, Audio, PDF).

### 2.2 Rich Interactive Content Blocks
Teachers assemble lesson activities using modular content blocks:
- **Rich Text & Math Blocks:** Full Markdown, LaTeX mathematical formula rendering, highlighted callout quotes, and embedded images.
- **Video & Lecture Streaming:** Responsive video streaming with speed controls, closed captions, chapter timestamps, and resume-playback memory.
- **Interactive Checkpoint Quizzes:** Low-stakes formative knowledge checks embedded directly inside reading material (e.g., multiple choice, true/false, fill-in-the-blank).
- **Interactive Code Playgrounds:** Executable code sandboxes for computer science subjects supporting HTML, CSS, JavaScript, and Python.
- **SCORM / External Packages:** Full support for industry-standard SCORM 1.2 / 2004 interactive learning objects.

### 2.3 Curricular Access Controls & Content Gating
- **Publishing Lifecycle:** Courses, chapters, and activities maintain distinct states (`Draft`, `Under Department Review`, `Published`, `Archived`).
- **Gating & Lock Types:**
  - *Public / Open:* Free access for all registered students.
  - *Authenticated Enrolled:* Access restricted strictly to students with active Tier 2 Course Enrollments.
  - *Prerequisite-Locked:* Chapter unlocked only after passing the previous chapter's mastery checkpoint.
  - *Date-Released:* Content automatically appears according to the term's instructional calendar.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-LMS-001** | Unenrolled students or visitors cannot access restricted course activities or content blocks. | System displays enrollment requirement banner; blocks content delivery. |
| **VAL-LMS-002** | Editing a published course activity that students have already interacted with creates a new version, preserving historical submission snapshots. | System triggers version increment; protects student submission integrity. |
| **VAL-LMS-003** | Sequential progression cannot be bypassed if the course configuration enforces "Must Complete Prior Activity". | Downstream activities remain locked until completion event is recorded. |

---

## 4. Operational User Workflows

### 4.1 Lesson Creation & Publishing Workflow (Teacher)
1. The Physics teacher opens "AP Physics 1" in the Course Studio.
2. The teacher adds "Lesson 4.1: Momentum and Impulse" under Chapter 4.
3. The teacher drags in a Video Block (12-minute lab demonstration), followed by a Rich Text Block explaining momentum equations, and ends with a 3-question Checkpoint Quiz Block.
4. The teacher configures gating: "Students must achieve 100% on the Checkpoint Quiz to unlock Lesson 4.2".
5. The teacher clicks "Publish", instantly making the lesson available to the enrolled Grade 11-A batch.

---

## 5. Business Value & Strategic Impact
- **Higher Student Engagement:** Replaces passive textbook reading with dynamic, multimedia-rich interactive learning.
- **Pedagogical Autonomy for Teachers:** Gives faculty an intuitive, drag-and-drop authoring tool that requires zero coding expertise.
- **Consistent Curriculum Standards:** Department heads can review and enforce standardized course content across all campus sections.
