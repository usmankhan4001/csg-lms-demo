# Business Requirements: Campuses & Facilities Management

**Requirement ID:** BFR-ACAD-003  
**Domain:** Academic Core & School Operations (SMS)  
**Stakeholders:** Facilities Directors, Campus Operations Managers, School Principals, Timetable Schedulers  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

Educational organizations operate physical schools, multi-branch campuses, and hybrid facilities. Classrooms have physical capacity constraints, laboratories require specialized safety apparatus, and scheduling algorithms must prevent room double-booking or assigning 35 students to a 20-seat seminar room.

The **Campuses & Facilities Management** module governs the physical and logistical infrastructure of the school network. It catalogs multi-campus locations, campus buildings, physical classrooms, science laboratories, lecture halls, and virtual meeting spaces, tracking maximum seating capacity and facility equipment profiles.

---

## 2. Core Business Capabilities & Rules

### 2.1 Multi-Campus Branch Management
- **Campus Directory:** Manage multiple physical campus branches (e.g., "Downtown Main Campus", "West Suburban Campus", "North Sports Academy").
- **Campus Properties:** Physical address, contact phone/email, emergency coordinator contact, time zone, and operating hours.
- **Operational Independence:** Each campus can maintain independent bell schedules, holiday adjustments, and facility allocations while sharing the central educational programs.

### 2.2 Buildings & Wings Directory
- **Building Hierarchy:** Catalog distinct physical structures within each campus (e.g., "Science & Technology Wing", "Humanities Building", "Performing Arts Center", "Athletic Complex").
- **Building Attributes:** Floor count, accessibility features (wheelchair access, elevator status), emergency fire exits, and safety inspection certifications.

### 2.3 Rooms, Classrooms & Specialized Laboratories
- **Room Directory:** Catalog all instructional and non-instructional spaces (e.g., "Room 204", "Chemistry Lab A", "Computer Lab 2", "Auditorium", "Main Gymnasium").
- **Crucial Capacity Constraints:**
  - *Standard Seating Capacity:* The maximum number of students permitted under local building/safety codes.
  - *Exam Capacity:* The reduced seating capacity enforced during formal testing to prevent cheating (e.g., 50% spacing).
- **Room Types & Equipment Profiles:**
  - *Standard Classroom:* Desks, whiteboard, interactive projector.
  - *Science Laboratory:* Gas valves, fume hoods, sinks, safety eye-wash stations (specialized safety rules apply).
  - *Computer Laboratory:* Fixed workstations, network ports, software licenses.
  - *Performing Arts / Studio:* Acoustic soundproofing, instruments, performance stage.
  - *Virtual Classroom:* Dedicated WebRTC / live video room for remote or hybrid classes.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-FAC-001** | A physical room cannot be scheduled for two concurrent instructional or examination events on the same campus. | Timetable scheduler flags a hard room collision and refuses publication. |
| **VAL-FAC-002** | The enrolled student count of a batch or section cannot exceed the physical seating capacity of its assigned classroom. | System alerts administrator of an overcrowding safety violation. |
| **VAL-FAC-003** | Courses requiring specialized laboratory facilities (e.g., AP Chemistry Lab) can only be scheduled into rooms marked with the corresponding laboratory type. | Scheduling tool restricts room selection to qualified lab spaces. |

---

## 4. Operational User Workflows

### 4.1 Room Allocation & Capacity Audit Workflow (Facilities Manager)
1. At the start of the semester, the Facilities Manager audits all rooms in the "Science Building".
2. The manager updates "Physics Lab 102" capacity to 24 students following new laboratory bench installations.
3. When the automated Timetable Engine attempts to place a 28-student Physics section into Room 102, the system blocks the allocation, proposing the larger "Multi-Disciplinary Science Hall" instead.

---

## 5. Business Value & Strategic Impact
- **Child Safety & Fire Code Compliance:** Strictly eliminates classroom overcrowding and ensures adherence to local municipal building safety codes.
- **Optimized Capital Asset Utilization:** Generates room utilization heatmaps showing idle periods, enabling schools to repurpose underused facilities.
- **Seamless Scheduling:** Prevents embarrassing classroom double-booking and eliminates last-minute room reassignments.
