# Business Requirements: Transport Fleet Management

**Requirement ID:** BFR-OPS-003  
**Domain:** Institutional Administration & Finance  
**Stakeholders:** Transport Directors, Fleet Coordinators, School Bus Drivers, Campus Security, Parents  
**Classification:** Pure Business Requirements Specification  

---

## 1. Business Need & Operational Overview

For schools operating dedicated transportation networks, moving hundreds of students safely between their homes and campus every morning and afternoon is a mission-critical logistical operation. Parents demand real-time visibility into bus locations and pickup delays, while school administrators must enforce strict vehicle seating capacities, optimize transit routes, and verify driver credentials.

The **Transport Fleet Management** module governs school vehicle inventories, bus transit routes, driver and chaperone assignments, student seat allocations, and daily transit attendance.

---

## 2. Core Business Capabilities & Rules

### 2.1 Vehicle Fleet & Driver Directory
- **Vehicle Inventory:** Catalogs school-owned and contracted fleet vehicles (Buses, Mini-Vans, Shuttles).
- **Vehicle Attributes:** License plate, VIN, seating capacity (e.g., 48 passenger seats), maintenance logs, insurance policy expiration, and annual state safety inspection clearances.
- **Driver & Chaperone Records:** Driver commercial licenses, medical fitness certifications, clean driving records, and designated on-bus student chaperones.

### 2.2 Bus Transit Routes & Stops
- **Route Definition:** Morning pickup routes and afternoon drop-off routes (e.g., "Route 12 - North Hills Suburban Express").
- **Sequential Stops:** Ordered sequence of physical pickup/drop-off stops with scheduled arrival times (e.g., Stop 1: 7:15 AM, Stop 2: 7:22 AM, Campus Arrival: 7:50 AM).
- **Route Optimization:** Balances travel times to ensure student transit duration does not exceed reasonable limits (e.g., maximum 45 minutes on bus).

### 2.3 Student Seat Allocation & Bus Attendance
- **Seat Allocation:** Students subscribing to transportation services are assigned a specific bus route, pickup stop, and reserved seat number.
- **Capacity Constraint:** Total assigned students on a route cannot exceed the physical seating capacity of the assigned vehicle (zero standing passengers allowed).
- **Daily Bus Roll Call:** Drivers or chaperones log student boarding and disembarking via the mobile transport app (or RFID card tap), providing parents with real-time boarding notifications.

---

## 3. Business Validation Invariants & Edge Cases

| Invariant ID | Business Rule Description | Violation Outcome |
|---|---|---|
| **VAL-TRN-001** | Total students allocated to a bus route cannot exceed the certified passenger seating capacity of the assigned vehicle. | System blocks additional student seat allocations; alerts transport coordinator. |
| **VAL-TRN-002** | A vehicle cannot be dispatched on an active student route if its mandatory safety inspection or commercial insurance has expired. | Fleet management locks vehicle; dispatches replacement vehicle alert. |
| **VAL-TRN-003** | When an afternoon drop-off route is delayed by more than 15 minutes due to traffic or weather, an automated broadcast must alert all affected parents. | Automated delay alert dispatched to parent mobile apps on that route. |

---

## 4. Operational User Workflows

### 4.1 Bus Allocation & Daily Boarding Workflow (Coordinator & Parent)
1. During enrollment, a parent opts into transportation service for their Grade 4 daughter.
2. The Transport Coordinator reviews the residential address, assigns her to "Route 5 - Oak Ridge", Stop 3 (7:25 AM pickup).
3. On the first day of school, the student boards the bus and taps her RFID student badge.
4. The driver's tablet registers her presence; the parent instantly receives a push alert: *"Chloe boarded Bus 5 at Oak Ridge Stop at 7:26 AM."*
5. At 7:55 AM, the bus arrives at the school gate; a second alert confirms safe arrival on campus.

---

## 5. Business Value & Strategic Impact
- **Peace of Mind for Parents:** Real-time boarding notifications eliminate parental anxiety regarding child transit safety.
- **Strict Vehicle Safety Compliance:** Guarantees zero bus overcrowding and eliminates the dispatch of uncertified or uninspected vehicles.
- **Efficient Transportation Operations:** Route balancing minimizes fuel consumption and optimizes fleet vehicle utilization.
