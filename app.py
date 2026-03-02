from flask import Flask, render_template

# configure Flask so that the existing "a" directory is served as static
# (images can be accessed at /a/filename.jpg)
app = Flask(__name__, static_folder='a', static_url_path='/a')

@app.route('/')
def home():
    # simply render the provided index template
    return render_template('index.html')


# helper to gather directory structure of curriculum files under 'b' folder
import os
import sqlite3
from flask import url_for

DB_PATH = 'curriculum.db'


def init_db():
    """Ensure the SQLite database and table exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            dept TEXT,
            subject TEXT,
            category TEXT,
            semester TEXT,
            name TEXT,
            relpath TEXT
        )
        '''
    )
    conn.commit()
    conn.close()


def rebuild_db():
    """Scan the filesystem and repopulate the database.
    Call this when you add new materials or on startup if the DB is missing.
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM files')

    # المجلدات التي تحتوي على المناهج
    roots = [str(i) for i in range(1, 11)]
    
    for root in roots:
        if not os.path.isdir(root):
            continue

        for dept in os.listdir(root):
            dept_path = os.path.join(root, dept)
            if not os.path.isdir(dept_path):
                continue
            for subj in os.listdir(dept_path):
                subj_path = os.path.join(dept_path, subj)
                if not os.path.isdir(subj_path):
                    continue
                for level3 in os.listdir(subj_path):
                    level3_path = os.path.join(subj_path, level3)
                    if not os.path.isdir(level3_path):
                        continue
                    
                    # التحقق هل المجلد في المستوى الثالث هو "فصل دراسي" (خريف، ربيع، 202، عام) 
                    # أم هو "محتوى" (شيتات، ملخصات، اكواد)
                    semester_keywords = ['خريف', 'ربيع', 'فصل', 'ترم', '202', 'عام', 'سمستر', 'فـصل']
                    is_level3_semester = any(kw in level3 for kw in semester_keywords)
                    
                    # look for level 4 folders inside level 3
                    found_level4 = False
                    for level4 in os.listdir(level3_path):
                        level4_path = os.path.join(level3_path, level4)
                        if not os.path.isdir(level4_path):
                            continue
                        found_level4 = True
                        
                        # إذا كان المستوى 3 هو فصل دراسي والمستوى 4 هو محتوى، نقوم بقلبهم في قاعدة البيانات
                        # لضمان أن الترتيب دائماً: المحتوى -> الفصل الدراسي
                        if is_level3_semester:
                            # level3 is semester, level4 is category
                            cat, sem = level4, level3
                        else:
                            # level3 is category, level4 is semester
                            cat, sem = level3, level4

                        for dirpath, dirnames, filenames in os.walk(level4_path):
                            for fname in filenames:
                                # relpath relative to project root to include the folder number (1-10)
                                rel = os.path.relpath(os.path.join(dirpath, fname), '.').replace('\\', '/')
                                c.execute(
                                    'INSERT INTO files (dept,subject,category,semester,name,relpath) VALUES (?,?,?,?,?,?)',
                                    (dept, subj, cat, sem, fname, rel)
                                )
                    
                    # إذا لم توجد مجلدات في المستوى الرابع
                    if not found_level4:
                        if is_level3_semester:
                            # لو المستوى 3 فصل دراسي ومافيش جواه مجلدات، نعتبر المحتوى 'عام'
                            cat, sem = 'عام', level3
                        else:
                            # لو المستوى 3 محتوى ومافيش جواه مجلدات، نعتبر الفصل 'عام'
                            cat, sem = level3, 'عام'

                        for f in os.listdir(level3_path):
                            fpath = os.path.join(level3_path, f)
                            if os.path.isfile(fpath):
                                # relpath relative to project root to include the folder number (1-10)
                                rel = os.path.relpath(fpath, '.').replace('\\', '/')
                                c.execute(
                                    'INSERT INTO files (dept,subject,category,semester,name,relpath) VALUES (?,?,?,?,?,?)',
                                    (dept, subj, cat, sem, f, rel)
                                )
    conn.commit()
    conn.close()


def get_structure():
    """Read the nested structure from the database. Always refresh before reading
    so that newly added files are included automatically.
    """
    init_db()
    rebuild_db()

    structure = {}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # استخدام الأعمدة التي قمنا بترتيبها في rebuild_db بدلاً من المسار الفيزيائي
    for (dept, subj, cat, sem, name, rel) in c.execute('SELECT dept, subject, category, semester, name, relpath FROM files'):
        # بناء الهيكل بترتيب صارم: القسم -> المادة -> المحتوى -> الفصل الدراسي
        d_node = structure.setdefault(dept, {})
        s_node = d_node.setdefault(subj, {})
        c_node = s_node.setdefault(cat, {})
        sem_node = c_node.setdefault(sem, {})
        
        sem_node.setdefault('__files__', []).append({
            'name': name,
            'url': f'/files/{rel}'
        })
    conn.close()

    return structure


@app.route('/curriculum')
def curriculum():
    # build the structure of available documents
    structure = get_structure()
    return render_template('curriculum.html', structure=structure)


@app.route('/start-journey')
def start_journey():
    # Get subjects from database to populate tools
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # We'll map subjects to weights and types for the tools
    # In a real app, these would be in the DB, here we'll simulate logic
    subjects_data = []
    rows = c.execute('SELECT DISTINCT subject FROM files').fetchall()
    
    for row in rows:
        name = row[0]
        # logic to assign weight/type based on keywords
        weight = 3.0
        stype = 'mixed'
        
        lower_name = name.lower()
        if any(kw in lower_name for kw in ['برمجة', 'كود', 'java', 'python', 'c#', 'شيئية', 'مرئية']):
            weight = 5.0 # مواد برمجية تحتاج وقت أكثر
            stype = 'programming'
        elif any(kw in lower_name for kw in ['رياضيات', 'إحصاء', 'خوارزميات', 'منطق', 'جبر']):
            weight = 5.0 # مواد رياضيات تحتاج وقت أكثر
            stype = 'math'
        elif any(kw in lower_name for kw in ['تصميم', 'نظم', 'إدارة', 'ثقافة', 'هندسة', 'تحليل']):
            weight = 2.5 # مواد تعتمد على الحفظ والفهم النظري
            stype = 'theory'
        else:
            weight = 3.5
            stype = 'mixed'
            
        subjects_data.append({'name': name, 'weight': weight, 'type': stype})
    
    conn.close()
    return render_template('a.html', subjects=subjects_data)


# utility endpoint to rebuild the database (called manually after adding files)
@app.route('/refresh')
def refresh():
    rebuild_db()
    return 'database refreshed'


# serve any file under the b directory for download
from flask import send_from_directory

@app.route('/files/<path:filename>')
def files(filename):
    # Removing as_attachment=True allows the browser to display PDFs in the iframe
    # Serve from the root directory because the filename now includes the folder number (e.g., 1/...)
    return send_from_directory('.', filename)

if __name__ == '__main__':
    # run in debug mode by default
    app.run(debug=True)
