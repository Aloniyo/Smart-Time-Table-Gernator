import pandas as pd
from datetime import datetime, timedelta

class TimetableGenerator:
    def __init__(self, input_file, max_teacher_credits=18):
        self.input_file = input_file
        self.max_teacher_credits = max_teacher_credits
        self.data_df = None
        self.faculty = {}
        self.classes = {}
        self.schedule = pd.DataFrame(columns=["Class", "Subject", "Type", "Faculty", "Timeslot", "Classroom"])
        self.used_timeslots = {}
        self.faculty_workload = {}
        self.teacher_schedules = {}
        self.class_schedules = {}
        self.classrooms = []
        self.morning_timeslots = []
        self.noon_timeslots = []
        self.selected_semester = None
        self.break_timeslot = None

    def ask_semester(self):
        self.selected_semester = input("Enter the semester for which you want to create the timetable: ").strip()

    def ask_for_break(self):
        add_break = input("Do you want to add a break? (yes/no): ").strip().lower()
        if add_break == "yes":
            self.break_timeslot = input("Enter the break timing (e.g., 10:30 - 10:50): ").strip()

    def load_data(self):
        self.data_df = pd.read_excel(self.input_file)
        self.data_df.columns = self.data_df.columns.str.strip()
        self.data_df = self.data_df[self.data_df["Semester"].astype(str) == self.selected_semester]

    def prepare_faculty_subject_mapping(self):
        for _, row in self.data_df.iterrows():
            faculty_name = str(row["Faculty Name"]).strip() if pd.notna(row["Faculty Name"]) else "Unknown"
            subject = str(row["Subjects"]).strip() if pd.notna(row["Subjects"]) else "Unknown"
            
            if subject not in self.faculty:
                self.faculty[subject] = []
            self.faculty[subject].append(faculty_name)
            self.faculty_workload.setdefault(faculty_name, 0)
            self.teacher_schedules.setdefault(faculty_name, set())

    def prepare_class_subject_mapping(self):
        for _, row in self.data_df.iterrows():
            class_name = row["Classes"].strip()
            semester = row["Semester"].strip()
            subject = row["Subjects"].strip()
            theory_credits = row["Theory"] if pd.notna(row["Theory"]) else 0
            practical_credits = row["Practical"] if pd.notna(row["Practical"]) else 0
            shift = row["Shift"].strip().lower()
            class_size = row["Class Size"]
            class_key = f"{class_name}Sem{semester}{shift}"
            if class_key not in self.classes:
                self.classes[class_key] = {"shift": shift, "subjects": {}, "size": class_size}
                self.class_schedules[class_key] = set()
            self.classes[class_key]["subjects"][subject] = {
                'theory': theory_credits,
                'practical': practical_credits
            }

    def generate_timeslots(self, start, end):
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        start_time = datetime.strptime(start, "%H:%M")
        end_time = datetime.strptime(end, "%H:%M")
        timeslots = []
        for day in days:
            current_time = start_time
            while current_time + timedelta(minutes=50) <= end_time:
                slot = f"{day} {current_time.strftime('%H:%M')} - {(current_time + timedelta(minutes=50)).strftime('%H:%M')}"
                if self.break_timeslot and self.break_timeslot in slot:
                    current_time += timedelta(minutes=50)
                    continue
                timeslots.append(slot)
                current_time += timedelta(minutes=50)
        return timeslots

    def find_best_teacher(self, subject):
        if subject not in self.faculty:
            return None
        available_teachers = sorted(
            [teacher for teacher in self.faculty[subject] if self.faculty_workload[teacher] < self.max_teacher_credits],
            key=lambda t: self.faculty_workload[t]
        )
        return available_teachers[0] if available_teachers else None

    def schedule_lectures(self, classrooms, room_capacity):
        self.classrooms = classrooms
        self.used_timeslots = {room: set() for room in self.classrooms}
        schedule_list = []

        for class_name, class_info in self.classes.items():
            shift = class_info["shift"]
            subjects = class_info["subjects"]
            class_size = class_info["size"]
            timeslots = self.morning_timeslots if shift == "m" else self.noon_timeslots
            
            subject_lecture_queue = []
            for subject, details in subjects.items():
                assigned_teacher = self.find_best_teacher(subject)
                if not assigned_teacher:
                    print(f"Warning: No suitable teacher found for {subject} in {class_name}")
                    continue
                theory_credits = details['theory']
                practical_credits = details['practical']
                subject_lecture_queue.extend([(subject, 'Theory', assigned_teacher, 1) for _ in range(int(theory_credits))])
                subject_lecture_queue.extend([(subject, 'Practical', assigned_teacher, 2) for _ in range(int(practical_credits))])

            for lecture in subject_lecture_queue:
                subject, lecture_type, teacher, slots_needed = lecture
                scheduled = False
                for i in range(len(timeslots)):
                    current_slot = timeslots[i]
                    current_day = current_slot.split()[0]
                    if current_slot in self.class_schedules[class_name]:
                        continue
                    for room in self.classrooms:
                        if room_capacity.get(room, 0) < class_size:
                            continue
                        if lecture_type == 'Theory':
                            if current_slot not in self.used_timeslots[room]:
                                schedule_list.append({
                                    "Class": class_name,
                                    "Subject": subject,
                                    "Type": lecture_type,
                                    "Faculty": teacher,
                                    "Timeslot": current_slot,
                                    "Classroom": room
                                })
                                self.used_timeslots[room].add(current_slot)
                                self.class_schedules[class_name].add(current_slot)
                                self.faculty_workload[teacher] += 1
                                self.teacher_schedules[teacher].add(current_slot)
                                scheduled = True
                                break
                        elif lecture_type == 'Practical':
                            if i + 1 >= len(timeslots):
                                continue
                            next_slot = timeslots[i + 1]
                            next_day = next_slot.split()[0]
                            if current_day != next_day:
                                continue
                            if (current_slot not in self.used_timeslots[room] and
                                next_slot not in self.used_timeslots[room] and
                                current_slot not in self.class_schedules[class_name] and
                                next_slot not in self.class_schedules[class_name]):
                                schedule_list.append({
                                    "Class": class_name,
                                    "Subject": subject,
                                    "Type": lecture_type,
                                    "Faculty": teacher,
                                    "Timeslot": current_slot,
                                    "Classroom": room
                                })
                                schedule_list.append({
                                    "Class": class_name,
                                    "Subject": subject,
                                    "Type": lecture_type,
                                    "Faculty": teacher,
                                    "Timeslot": next_slot,
                                    "Classroom": room
                                })
                                self.used_timeslots[room].update([current_slot, next_slot])
                                self.class_schedules[class_name].update([current_slot, next_slot])
                                self.faculty_workload[teacher] += 1
                                self.teacher_schedules[teacher].update([current_slot, next_slot])
                                scheduled = True
                                break
                        if scheduled:
                            break
                    if scheduled:
                        break
                if not scheduled:
                    print(f"Warning: Could not schedule {lecture_type} for {subject} in {class_name}")

        self.schedule = pd.concat([self.schedule, pd.DataFrame(schedule_list)], ignore_index=True)

    def update_schedule(self, class_name, old_timeslot, new_timeslot=None, new_classroom=None, new_faculty=None, new_subject=None):
        index = self.schedule[
            (self.schedule["Class"] == class_name) & (self.schedule["Timeslot"] == old_timeslot)
        ].index

        if index.empty:
            print(f"❌ No matching entry found for {class_name} at {old_timeslot}.")
            return

        idx = index[0]

        current_entry = self.schedule.iloc[idx]
        current_subject = current_entry["Subject"]
        current_type = current_entry["Type"]
        current_faculty = current_entry["Faculty"]
        current_classroom = current_entry["Classroom"]
        current_timeslot = current_entry["Timeslot"]

        if current_type == 'Practical':
            paired_index = self.schedule[
                (self.schedule["Class"] == class_name) &
                (self.schedule["Subject"] == current_subject) &
                (self.schedule["Faculty"] == current_faculty) &
                (self.schedule["Timeslot"] != current_timeslot) &
                (self.schedule["Classroom"] == current_classroom)
            ].index
            if len(paired_index) != 1:
                print("Error: Practical session not properly paired.")
                return
            paired_idx = paired_index[0]

        self.used_timeslots[current_classroom].remove(current_timeslot)
        self.class_schedules[class_name].remove(current_timeslot)
        self.teacher_schedules[current_faculty].remove(current_timeslot)

        if current_type == 'Practical':
            paired_timeslot = self.schedule.iloc[paired_idx]["Timeslot"]
            self.used_timeslots[current_classroom].remove(paired_timeslot)
            self.class_schedules[class_name].remove(paired_timeslot)
            self.teacher_schedules[current_faculty].remove(paired_timeslot)

        if new_timeslot:
            if any(new_timeslot in self.used_timeslots[room] for room in self.classrooms):
                print(f"⚠️ Conflict detected: {new_timeslot} is already booked. Choose another slot.")
                return
            self.schedule.at[idx, "Timeslot"] = new_timeslot
            self.used_timeslots[new_classroom if new_classroom else current_classroom].add(new_timeslot)
            self.class_schedules[class_name].add(new_timeslot)
            self.teacher_schedules[current_faculty if not new_faculty else new_faculty].add(new_timeslot)
            if current_type == 'Practical':
                new_paired_slot = self.find_next_consecutive_slot(new_timeslot)
                if new_paired_slot:
                    self.schedule.at[paired_idx, "Timeslot"] = new_paired_slot
                    self.used_timeslots[new_classroom if new_classroom else current_classroom].add(new_paired_slot)
                    self.class_schedules[class_name].add(new_paired_slot)
                    self.teacher_schedules[current_faculty if not new_faculty else new_faculty].add(new_paired_slot)
                else:
                    print("Warning: Could not find consecutive slot for practical.")

        if new_classroom:
            self.schedule.at[idx, "Classroom"] = new_classroom
            self.used_timeslots[new_classroom].add(new_timeslot if new_timeslot else current_timeslot)
            if current_type == 'Practical':
                self.schedule.at[paired_idx, "Classroom"] = new_classroom
                self.used_timeslots[new_classroom].add(self.schedule.iloc[paired_idx]["Timeslot"])

        if new_faculty:
            self.faculty_workload[current_faculty] -= 1
            self.faculty_workload[new_faculty] += 1
            self.schedule.at[idx, "Faculty"] = new_faculty
            if current_type == 'Practical':
                self.schedule.at[paired_idx, "Faculty"] = new_faculty

        if new_subject:
            self.schedule.at[idx, "Subject"] = new_subject
            if current_type == 'Practical':
                self.schedule.at[paired_idx, "Subject"] = new_subject

        print(f"✅ Successfully updated schedule for {class_name} at {new_timeslot if new_timeslot else current_timeslot}.")

    def find_next_consecutive_slot(self, slot):
        day, start_end = slot.split(' ', 1)
        start_time = datetime.strptime(start_end.split(' - ')[0], "%H:%M")
        next_start = start_time + timedelta(minutes=50)
        next_slot = f"{day} {next_start.strftime('%H:%M')} - {(next_start + timedelta(minutes=50)).strftime('%H:%M')}"
        return next_slot if next_slot in self.morning_timeslots + self.noon_timeslots else None

    def save_timetable(self, output_file):
        with pd.ExcelWriter(output_file) as writer:
            self.schedule.to_excel(writer, sheet_name="Full Schedule", index=False)

            classwise = self.schedule.copy()
            classwise["Merged"] = classwise.apply(lambda x: f"{x['Subject']} ({x['Type']}) - {x['Faculty']} - {x['Classroom']}", axis=1)
            classwise_pivot = classwise.pivot_table(index="Timeslot", columns="Class", values="Merged", aggfunc=lambda x: ' | '.join(x))
            classwise_pivot.to_excel(writer, sheet_name="Class-wise")

            facultywise = self.schedule.copy()
            facultywise["Merged"] = facultywise.apply(lambda x: f"{x['Subject']} ({x['Type']}) - {x['Class']} - {x['Classroom']}", axis=1)
            facultywise_pivot = facultywise.pivot_table(index="Timeslot", columns="Faculty", values="Merged", aggfunc=lambda x: ' | '.join(x))
            facultywise_pivot.to_excel(writer, sheet_name="Faculty-wise")

            classroomwise = self.schedule.copy()
            classroomwise["Merged"] = classroomwise.apply(lambda x: f"{x['Subject']} ({x['Type']}) - {x['Class']} - {x['Faculty']}", axis=1)
            classroomwise_pivot = classroomwise.pivot_table(index="Timeslot", columns="Classroom", values="Merged", aggfunc=lambda x: ' | '.join(x))
            classroomwise_pivot.to_excel(writer, sheet_name="Classroom-wise")

        print(f"Timetable saved successfully to {output_file}")

# Usage
input_file = "data.xlsx"
output_file = "Output.xlsx"
timetable = TimetableGenerator(input_file)
timetable.ask_semester()
timetable.ask_for_break()
timetable.load_data()
timetable.prepare_faculty_subject_mapping()
timetable.prepare_class_subject_mapping()
timetable.morning_timeslots = timetable.generate_timeslots("08:00", "12:00")
timetable.noon_timeslots = timetable.generate_timeslots("13:00", "17:00")

room_capacity = {"D1": 60, "D2": 50, "D3": 40, "D4": 30, "D5": 60}
timetable.schedule_lectures(["D1", "D2", "D3", "D4", "D5"], room_capacity)
timetable.save_timetable(output_file)

# Example update calls (commented out)
# timetable.update_schedule("BCASemSecondm", "Thursday 09:40 - 10:30", new_timeslot="Tuesday 10:00 - 10:50", new_classroom="D5", new_faculty="Dr. Smith", new_subject="Data Structures")
