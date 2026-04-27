import secrets
import csv
import io
import os
import random
from datetime import datetime
from functools import wraps
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, Quiz, Question, Option, StudentResult, Teacher, SchoolClass
from extensions import limiter, socketio

main_bp = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('main.teacher_login'))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.before_app_request
def check_setup():
    if request.endpoint and 'static' not in request.endpoint:
        teacher = Teacher.query.first()
        # If no teacher exists and we are not on the setup page, redirect to setup
        if not teacher and request.endpoint != 'main.setup':
            return redirect(url_for('main.setup'))
        # If teacher exists and we try to access setup, redirect to login
        if teacher and request.endpoint == 'main.setup':
             return redirect(url_for('main.teacher_login'))

@main_bp.route('/')
def landing():
    return render_template('landing.html')

@main_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        
        if password != confirm:
            flash('Les mots de passe ne correspondent pas.')
            return render_template('setup.html')
            
        if Teacher.query.filter_by(username=username).first():
            flash('Ce nom d\'utilisateur existe déjà.')
            return render_template('setup.html')
            
        recovery_code = secrets.token_hex(16)
        hashed_code = generate_password_hash(recovery_code)
        hashed_password = generate_password_hash(password)
        
        teacher = Teacher(
            username=username,
            password_hash=hashed_password,
            recovery_code_hash=hashed_code
        )
        db.session.add(teacher)
        db.session.commit()
        
        return render_template('setup.html', recovery_code=recovery_code)
        
    return render_template('setup.html')

# --- Teacher Routes ---
@main_bp.route('/teacher/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def teacher_login():
    if request.method == 'POST':
        password = request.form.get('password')
        teacher = Teacher.query.first()
        
        if teacher and check_password_hash(teacher.password_hash, password): 
            session['logged_in'] = True
            return redirect(url_for('main.dashboard'))
        else:
            flash('Mot de passe incorrect')
    return render_template('teacher_login.html')

@main_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        recovery_code = request.form.get('recovery_code')
        new_password = request.form.get('new_password')
        
        teacher = Teacher.query.first() # Assume single teacher
        
        if teacher and check_password_hash(teacher.recovery_code_hash, recovery_code):
            teacher.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Mot de passe réinitialisé avec succès.')
            return redirect(url_for('main.teacher_login'))
        else:
            flash('Code de récupération invalide.')
            
    return render_template('reset_password.html')

@main_bp.route('/trigger_emergency_code', methods=['POST'])
def trigger_emergency_code():
    teacher = Teacher.query.first()
    if teacher:
        new_code = secrets.token_hex(8)
        teacher.recovery_code_hash = generate_password_hash(new_code)
        db.session.commit()
        
        print("\n=======================================================")
        print("!!! EMERGENCY RECOVERY CODE GENERATED !!!")
        print(f"NEW RECOVERY CODE: {new_code}")
        print("Please copy this code and use it to reset your password.")
        print("=======================================================\n")
        
        flash('Un code d\'urgence a été envoyé sur la console du serveur.')
    else:
        flash('Aucun compte administrateur trouvé.')
        
    return redirect(url_for('main.reset_password'))

@main_bp.route('/teacher/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('main.landing'))

@main_bp.route('/teacher/dashboard')
@login_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    # Get all non-archived quizzes with pagination
    quizzes = Quiz.query.filter(or_(Quiz.is_archived == False, Quiz.is_archived == None)).order_by(Quiz.id.desc()).paginate(page=page, per_page=10)
    return render_template('teacher_dashboard.html', quizzes=quizzes)

@main_bp.route('/create_quiz', methods=['GET', 'POST'])
@login_required
def create_quiz():
    if request.method == 'POST':
        title = request.form.get('title')
        time_limit = request.form.get('time_limit')
        new_quiz = Quiz(title=title, time_limit_minutes=int(time_limit))
        db.session.add(new_quiz)
        db.session.commit()
        return redirect(url_for('main.add_question', quiz_id=new_quiz.id))
    return render_template('create_quiz.html')

@main_bp.route('/import_quiz', methods=['POST'])
@login_required
def import_quiz():
    if 'file' not in request.files:
        flash('Aucun fichier uploadé.')
        return redirect(url_for('main.dashboard'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Aucun fichier sélectionné.')
        return redirect(url_for('main.dashboard'))
        
    if file and file.filename.endswith('.json'):
        try:
            quiz_data = json.load(file)
            new_quiz = Quiz(
                title=quiz_data.get('title', 'Imported Quiz'),
                time_limit_minutes=quiz_data.get('time_limit_minutes', 30)
            )
            db.session.add(new_quiz)
            db.session.flush()
            
            for q_data in quiz_data.get('questions', []):
                new_q = Question(quiz_id=new_quiz.id, text=q_data.get('text', ''))
                db.session.add(new_q)
                db.session.flush()
                
                for opt_data in q_data.get('options', []):
                    new_opt = Option(
                        question_id=new_q.id,
                        text=opt_data.get('text', ''),
                        is_correct=opt_data.get('is_correct', False)
                    )
                    db.session.add(new_opt)
                    
            db.session.commit()
            flash('Quiz importé avec succès.')
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de l'importation : {str(e)}")
            
    return redirect(url_for('main.dashboard'))

@main_bp.route('/export_quiz/<int:quiz_id>')
@login_required
def export_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    quiz_data = {
        'title': quiz.title,
        'time_limit_minutes': quiz.time_limit_minutes,
        'questions': []
    }
    for q in quiz.questions:
        q_data = {
            'text': q.text,
            'options': [{'text': opt.text, 'is_correct': opt.is_correct} for opt in q.options]
        }
        quiz_data['questions'].append(q_data)
        
    return Response(
        json.dumps(quiz_data, indent=4),
        mimetype="application/json",
        headers={"Content-disposition": f"attachment; filename=quiz_{quiz_id}.json"}
    )

@main_bp.route('/add_question/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def add_question(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if request.method == 'POST':
        if 'finish' in request.form:
             return redirect(url_for('main.dashboard'))
             
        text = request.form.get('text')
        # Dynamic options processing
        # We expect inputs named 'options[]' and 'correct_answer_index'
        option_texts = request.form.getlist('options[]')
        correct_index = request.form.get('correct_answer_index')
        
        if text and option_texts and correct_index is not None:
            try:
                correct_idx = int(correct_index)
                if len(option_texts) < 2:
                     flash('Il faut au moins 2 options.')
                else:
                    q = Question(quiz_id=quiz.id, text=text)
                    db.session.add(q)
                    db.session.flush() # Generate ID
                    
                    for i, opt_text in enumerate(option_texts):
                        is_correct = (i == correct_idx)
                        opt = Option(question_id=q.id, text=opt_text, is_correct=is_correct)
                        db.session.add(opt)
                    
                    db.session.commit()
                    flash('Question ajoutée avec succès.')
            except ValueError:
                flash('Erreur de format des données.')
        else:
            flash('Veuillez remplir tous les champs.')
        
        return redirect(url_for('main.add_question', quiz_id=quiz.id))
    
    return render_template('add_question.html', quiz=quiz)

@main_bp.route('/delete_quiz/<int:quiz_id>', methods=['POST'])
@login_required
def delete_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    try:
        quiz.is_archived = True
        quiz.is_active = False
        db.session.commit()
        flash('Quiz archivé avec succès.')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur : {str(e)}')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/delete_question/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    q = Question.query.get_or_404(question_id)
    quiz_id = q.quiz_id
    try:
        db.session.delete(q)
        db.session.commit()
        flash('Question supprimée.')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur : {str(e)}')
    return redirect(url_for('main.add_question', quiz_id=quiz_id))

@main_bp.route('/edit_question/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    q = Question.query.get_or_404(question_id)
    if request.method == 'POST':
        q.text = request.form.get('text')
        
        # We need to replace options. 
        # Simples way: delete old options and create new ones
        option_texts = request.form.getlist('options[]')
        correct_index = request.form.get('correct_answer_index')
        
        if option_texts and correct_index is not None:
             try:
                correct_idx = int(correct_index)
                # Delete existing options
                Option.query.filter_by(question_id=q.id).delete()
                
                for i, opt_text in enumerate(option_texts):
                    is_correct = (i == correct_idx)
                    opt = Option(question_id=q.id, text=opt_text, is_correct=is_correct)
                    db.session.add(opt)
                    
                db.session.commit()
                flash('Question mise à jour.')
             except ValueError:
                 flash('Erreur lors de la mise à jour.')
        
        return redirect(url_for('main.add_question', quiz_id=q.quiz_id))
        
    return render_template('edit_question.html', question=q)

@main_bp.route('/teacher/results')
@login_required
def view_results():
    quiz_filter = request.args.get('quiz_id')
    class_filter = request.args.get('class_filter')
    sort_by = request.args.get('sort_by', 'date') # default sort by date
    
    quizzes = Quiz.query.all()
    # Get unique classes for filter dropdown
    classes = db.session.query(StudentResult.student_class).distinct().all()
    classes = [c[0] for c in classes if c[0]]
    
    query = StudentResult.query.join(Quiz).add_columns(
        StudentResult.id.label('result_id'),
        StudentResult.first_name, 
        StudentResult.last_name,
        StudentResult.student_class,
        StudentResult.score, 
        StudentResult.total_questions,
        StudentResult.date_taken,
        Quiz.title,
        Quiz.id.label('quiz_id')
    )
    
    selected_quiz = None
    if quiz_filter and quiz_filter != 'all':
        query = query.filter(Quiz.id == int(quiz_filter))
        selected_quiz = int(quiz_filter)
        
    if class_filter and class_filter != 'all':
        query = query.filter(StudentResult.student_class == class_filter)
        
    # Sorting
    if sort_by == 'name':
        query = query.order_by(StudentResult.last_name, StudentResult.first_name)
    elif sort_by == 'score':
        query = query.order_by((StudentResult.score * 1.0 / StudentResult.total_questions).desc())
    elif sort_by == 'class':
        query = query.order_by(StudentResult.student_class)
    else: # date
        query = query.order_by(StudentResult.date_taken.desc())
        
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 15, type=int)
    if per_page not in (15, 20, 25, 30, 50):
        per_page = 15
    results = query.paginate(page=page, per_page=per_page)
    return render_template('teacher_results.html', 
                         quizzes=quizzes, 
                         results=results, 
                         selected_quiz=selected_quiz,
                         classes=classes,
                         selected_class=class_filter,
                         current_sort=sort_by,
                         current_per_page=per_page)

@main_bp.route('/toggle_active/<int:quiz_id>', methods=['POST'])
@login_required
def toggle_active(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    was_active = quiz.is_active
    Quiz.query.update({Quiz.is_active: False})
    if not was_active:
        quiz.is_active = True
    db.session.commit()
    return redirect(url_for('main.dashboard'))

@main_bp.route('/download_results/<int:quiz_id>')
@login_required
def download_results(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    results = StudentResult.query.filter_by(quiz_id=quiz_id).all()

    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Excel compatibility
    writer = csv.writer(output)
    writer.writerow(['Prénom', 'Nom', 'Classe', 'Note /20', 'Score Brut', 'Total Questions', 'Date'])
    for r in results:
        score_on_20 = round((r.score / r.total_questions) * 20, 1) if r.total_questions > 0 else 0
        writer.writerow([
            r.first_name, r.last_name, r.student_class,
            score_on_20, r.score, r.total_questions,
            r.date_taken.strftime('%d/%m/%Y %H:%M') if r.date_taken else ''
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=results_{quiz.title}.csv'}
    )

@main_bp.route('/teacher/profile')
@login_required
def profile():
    teacher = Teacher.query.first()
    return render_template('teacher_profile.html', teacher=teacher)

@main_bp.route('/teacher/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    teacher = Teacher.query.first()
    
    if not check_password_hash(teacher.password_hash, current_password):
        flash('Mot de passe actuel incorrect.')
        return redirect(url_for('main.profile'))
        
    if new_password != confirm_password:
        flash('Les nouveaux mots de passe ne correspondent pas.')
        return redirect(url_for('main.profile'))
        
    teacher.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash('Mot de passe mis à jour avec succès.')
    return redirect(url_for('main.profile'))

@main_bp.route('/teacher/regenerate_recovery', methods=['POST'])
@login_required
def regenerate_recovery():
    teacher = Teacher.query.first()
    
    new_code = secrets.token_hex(16)
    teacher.recovery_code_hash = generate_password_hash(new_code)
    db.session.commit()
    
    flash('Nouveau code de récupération généré.')
    return render_template('teacher_profile.html', teacher=teacher, new_recovery_code=new_code)

# --- Class Management Routes ---
@main_bp.route('/teacher/classes')
@login_required
def manage_classes():
    classes = SchoolClass.query.order_by(SchoolClass.name).all()
    return render_template('manage_classes.html', classes=classes)

@main_bp.route('/teacher/classes/add', methods=['POST'])
@login_required
def add_class():
    name = request.form.get('class_name', '').strip().upper()
    if not name:
        flash('Le nom de la classe ne peut pas être vide.')
        return redirect(url_for('main.manage_classes'))
    
    existing = SchoolClass.query.filter_by(name=name).first()
    if existing:
        flash('Cette classe existe déjà.')
        return redirect(url_for('main.manage_classes'))
    
    new_class = SchoolClass(name=name)
    db.session.add(new_class)
    db.session.commit()
    flash(f'Classe "{name}" ajoutée avec succès.')
    return redirect(url_for('main.manage_classes'))

@main_bp.route('/teacher/classes/delete/<int:class_id>', methods=['POST'])
@login_required
def delete_class(class_id):
    school_class = SchoolClass.query.get_or_404(class_id)
    name = school_class.name
    db.session.delete(school_class)
    db.session.commit()
    flash(f'Classe "{name}" supprimée.')
    return redirect(url_for('main.manage_classes'))

# --- Student Routes ---
@main_bp.route('/student')
def student_login():
    classes = SchoolClass.query.order_by(SchoolClass.name).all()
    return render_template('student_login.html', classes=classes)

@main_bp.route('/join', methods=['POST'])
def join():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    student_class = request.form.get('student_class')
    
    if not first_name or not last_name or not student_class:
        flash('Veuillez remplir tous les champs.')
        return redirect(url_for('main.student_login'))
    
    active_quiz = Quiz.query.filter(
        Quiz.is_active == True,
        or_(Quiz.is_archived == False, Quiz.is_archived == None)
    ).first()
    
    if not active_quiz:
        return render_template('no_active_quiz.html')
        
    existing_result = StudentResult.query.filter(
        StudentResult.quiz_id == active_quiz.id,
        db.func.lower(StudentResult.first_name) == db.func.lower(first_name),
        db.func.lower(StudentResult.last_name) == db.func.lower(last_name),
        StudentResult.student_class == student_class
    ).first()
    
    if existing_result:
        flash('Vous avez déjà passé ce quiz.')
        return redirect(url_for('main.student_login'))
    
    # Record start time in session
    session[f'quiz_start_time_{active_quiz.id}'] = datetime.now().timestamp()
    
    # Prepare Randomized Questions
    questions_list = list(active_quiz.questions)
    random.shuffle(questions_list)
    
    prepared_questions = []
    for q in questions_list:
        # Load options for this question
        opts = list(q.options)
        random.shuffle(opts)
        
        prepared_questions.append({
            'id': q.id,
            'text': q.text,
            'options': opts # Pass Option objects directly
        })
    
    return render_template('take_quiz.html', 
                         quiz=active_quiz, 
                         questions=prepared_questions, 
                         student={'first': first_name, 'last': last_name, 'student_class': student_class})

@main_bp.route('/submit_quiz/<int:quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    first_name = request.form.get('student_first', '').strip()
    last_name = request.form.get('student_last', '').strip()
    student_class = request.form.get('student_class')
    
    existing_result = StudentResult.query.filter(
        StudentResult.quiz_id == quiz.id,
        db.func.lower(StudentResult.first_name) == db.func.lower(first_name),
        db.func.lower(StudentResult.last_name) == db.func.lower(last_name),
        StudentResult.student_class == student_class
    ).first()
    
    if existing_result:
        flash('Vous avez déjà soumis ce quiz.')
        return redirect(url_for('main.student_login'))
        
    quiz_start_time = session.get(f'quiz_start_time_{quiz.id}')
    if quiz_start_time:
        current_time = datetime.now().timestamp()
        time_limit_seconds = quiz.time_limit_minutes * 60
        # Add 10 seconds grace period
        if current_time > quiz_start_time + time_limit_seconds + 10:
            flash("Le temps imparti pour le quiz est écoulé. Votre soumission n'a pas été acceptée.")
            return redirect(url_for('main.student_login'))
    
    score = 0
    questions = quiz.questions
    for q in questions:
        selected_option_id = request.form.get(f'q_{q.id}')
        # Find if this option is correct
        if selected_option_id:
            opt = Option.query.get(selected_option_id)
            if opt and opt.is_correct and opt.question_id == q.id:
                score += 1
            
    # Save result
    result = StudentResult(
        quiz_id=quiz.id, 
        first_name=first_name, 
        last_name=last_name, 
        student_class=student_class,
        score=score, 
        total_questions=len(questions)
    )
    db.session.add(result)
    db.session.commit()
    
    total = len(questions)
    score_on_20 = round((score / total) * 20, 1) if total > 0 else 0
    
    socketio.emit('new_submission', {
        'first_name': first_name,
        'last_name': last_name,
        'quiz_id': quiz.id,
        'quiz_title': quiz.title,
        'score': score_on_20,
        'total': 20
    })
        
    return render_template('results.html', score=score, total=total, score_on_20=score_on_20, student_name=f"{first_name} {last_name}")

@main_bp.route('/delete_result/<int:result_id>', methods=['POST'])
@login_required
def delete_result(result_id):
    result = StudentResult.query.get_or_404(result_id)
    try:
        db.session.delete(result)
        db.session.commit()
        flash('Résultat supprimé avec succès.')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur : {str(e)}')
    return redirect(url_for('main.view_results'))
