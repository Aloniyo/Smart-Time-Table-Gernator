import pandas as pd
import random
from datetime import datetime, timedelta

class TimetableGenerator:
    def __init__(self, input_file, max_teacher_credits=18):
        self.input_file = input_file
        self.max_teacher_credits = max_teacher_credits
        self.data_df = None
        self.faculty = {}
        self.classes = {}
        self.schedule = pd.DataFrame(columns=["Class", "Subject", "Faculty", "Timeslot", "Classroom"])
        self.used_timeslots = {}
        self.faculty_workload = {}
        self.teacher_schedules = {}
        self.class_schedules = {}
        self.classroom_schedules = {}
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
            credits = row["Credits"]
            shift = row["Shift"].strip().lower()
            class_size = row["Class Size"]
            is_practical = str(row.get("Practical", "No")).strip().lower() == "yes"
            class_key = f"{class_name}Sem{semester}{shift}"
            
            if class_key not in self.classes:
                self.classes[class_key] = {"shift": shift, "subjects": {}, "size": class_size, "practical": {}}
                self.class_schedules[class_key] = set()
            
            self.classes[class_key]["subjects"][subject] = credits
            self.classes[class_key]["practical"][subject] = is_practical

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
            practical_subjects = class_info["practical"]
            class_size = class_info["size"]
            timeslots = self.morning_timeslots if shift == "m" else self.noon_timeslots
            random.shuffle(timeslots)

            subject_lecture_queue = []
            for subject, lecture_count in subjects.items():
                assigned_teacher = self.find_best_teacher(subject)
                if not assigned_teacher:
                    print(f"Warning: No suitable teacher found for {subject} in {class_name}")
                    continue
                is_practical = practical_subjects.get(subject, False)
                for _ in range(lecture_count):
                    subject_lecture_queue.append((subject, assigned_teacher, is_practical))
            
            random.shuffle(subject_lecture_queue)
            for i in range(len(timeslots) - 1):
                if not subject_lecture_queue:
                    break
                
                for room in self.classrooms:
                    if (
                        timeslots[i] not in self.used_timeslots[room] and
                        timeslots[i] not in self.class_schedules[class_name] and
                        room_capacity.get(room, 0) >= class_size
                    ):
                        subject, assigned_teacher, is_practical = subject_lecture_queue.pop(0)
                        
                        schedule_list.append({
                            "Class": class_name,
                            "Subject": subject,
                            "Faculty": assigned_teacher,
                            "Timeslot": timeslots[i],
                            "Classroom": room,
                        })
                        self.used_timeslots[room].add(timeslots[i])
                        self.class_schedules[class_name].add(timeslots[i])
                        self.faculty_workload[assigned_teacher] += 1
                        self.teacher_schedules[assigned_teacher].add(timeslots[i])
                        
                        if is_practical and i + 1 < len(timeslots):
                            schedule_list.append({
                                "Class": class_name,
                                "Subject": subject,
                                "Faculty": assigned_teacher,
                                "Timeslot": timeslots[i + 1],
                                "Classroom": room,
                            })
                            self.used_timeslots[room].add(timeslots[i + 1])
                            self.class_schedules[class_name].add(timeslots[i + 1])
                            self.faculty_workload[assigned_teacher] += 1
                            self.teacher_schedules[assigned_teacher].add(timeslots[i + 1])
                        break
        self.schedule = pd.concat([self.schedule, pd.DataFrame(schedule_list)], ignore_index=True)


    def update_schedule(self, class_name, old_timeslot, new_timeslot=None, new_classroom=None, new_faculty=None, new_subject=None):
        # Find the entry to update
        index = self.schedule[
            (self.schedule["Class"] == class_name) & (self.schedule["Timeslot"] == old_timeslot)
        ].index

        if index.empty:
            print(f"❌ No matching entry found for {class_name} at {old_timeslot}.")
            return

        idx = index[0]  # Get the first matching row index

        # Get current values
        current_subject = self.schedule.at[idx, "Subject"]
        current_faculty = self.schedule.at[idx, "Faculty"]
        current_classroom = self.schedule.at[idx, "Classroom"]

    # Remove old schedule references
        self.used_timeslots[current_classroom].remove(old_timeslot)
        self.class_schedules[class_name].remove(old_timeslot)
        self.teacher_schedules[current_faculty].remove(old_timeslot)

        if new_timeslot:
            # Check for conflicts before updating timeslot
            if any(new_timeslot in self.used_timeslots[room] for room in self.classrooms):
                print(f"⚠️ Conflict detected: {new_timeslot} is already booked. Choose another slot.")
                return
            self.schedule.at[idx, "Timeslot"] = new_timeslot
            self.used_timeslots[new_classroom if new_classroom else current_classroom].add(new_timeslot)
            self.class_schedules[class_name].add(new_timeslot)
            self.teacher_schedules[current_faculty if not new_faculty else new_faculty].add(new_timeslot)

        if new_classroom:
            self.schedule.at[idx, "Classroom"] = new_classroom
            self.used_timeslots[new_classroom].add(new_timeslot if new_timeslot else old_timeslot)

        if new_faculty:
            self.faculty_workload[current_faculty] -= 1  # Reduce workload for old faculty
            self.faculty_workload[new_faculty] += 1  # Assign workload to new faculty
            self.schedule.at[idx, "Faculty"] = new_faculty

        if new_subject:
            self.schedule.at[idx, "Subject"] = new_subject

        print(f"✅ Successfully updated schedule for {class_name} at {new_timeslot if new_timeslot else old_timeslot}.")
        timetable.save_timetable("output.xlsx")


    def save_timetable(self, output_file):
        with pd.ExcelWriter(output_file) as writer:
            self.schedule.to_excel(writer, sheet_name="Full Schedule", index=False)

            # Class-wise timetable (Timeslot vs Class with merged Subject, Faculty, Classroom)
            classwise = self.schedule.copy()
            classwise["Merged"] = classwise.apply(lambda x: f"{x['Subject']} ({x['Faculty']}) - {x['Classroom']}", axis=1)
            classwise_pivot = classwise.pivot_table(index="Timeslot", columns="Class", values="Merged", aggfunc=lambda x: ' | '.join(x))
            classwise_pivot.to_excel(writer, sheet_name="Class-wise")

            # Faculty-wise timetable (Timeslot vs Faculty with merged Subject, Class, Classroom)
            facultywise = self.schedule.copy()
            facultywise["Merged"] = facultywise.apply(lambda x: f"{x['Subject']} ({x['Class']}) - {x['Classroom']}", axis=1)
            facultywise_pivot = facultywise.pivot_table(index="Timeslot", columns="Faculty", values="Merged", aggfunc=lambda x: ' | '.join(x))
            facultywise_pivot.to_excel(writer, sheet_name="Faculty-wise")

            # Classroom-wise timetable (Timeslot vs Classroom with merged Subject, Class, Faculty)
            classroomwise = self.schedule.copy()
            classroomwise["Merged"] = classroomwise.apply(lambda x: f"{x['Subject']} ({x['Class']}) - {x['Faculty']}", axis=1)
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

timetable.update_schedule("BCASemSecondm", "Wednesday 08:50 - 09:40", new_timeslot="Tuesday 10:00 - 10:50", new_classroom="D5", new_faculty="Roshni Ramnani", new_subject="Psychology")
#timetable.update_schedule("BCASemSecondm", "Tuesday 09:00 - 09:50", new_subject="Data Structures")
#timetable.update_schedule("BCASemSecondm", "Tuesday 09:00 - 09:50", new_faculty="Dr. Smith")
#timetable.update_schedule("BCASemSecondm", "Tuesday 09:00 - 09:50", new_classroom="D5")
