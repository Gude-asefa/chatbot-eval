-- Reference schema. The app creates these automatically if missing (CREATE IF NOT EXISTS),
-- so you only need this if you created the tables by hand: yours must have these columns.

CREATE TABLE IF NOT EXISTS questions (
    question_id     VARCHAR(50)  PRIMARY KEY,
    department      VARCHAR(100) NOT NULL,
    section         VARCHAR(20)  NOT NULL,          -- 'Information' | 'Action'
    category        VARCHAR(100) NOT NULL,
    question_type   VARCHAR(30)  NOT NULL DEFAULT '',
    language        VARCHAR(20)  NOT NULL,          -- 'Amharic' | 'English'
    question_text   TEXT         NOT NULL,
    expected_answer TEXT         NOT NULL DEFAULT '',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ  NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_questions_department ON questions (department);

CREATE TABLE IF NOT EXISTS evaluations (
    id              SERIAL       PRIMARY KEY,
    tester_name     VARCHAR(200) NOT NULL,
    tester_key      VARCHAR(320) NOT NULL,          -- lower(department|name)
    department      VARCHAR(100) NOT NULL,
    section         VARCHAR(20)  NOT NULL,
    language        VARCHAR(20)  NOT NULL,
    question_id     VARCHAR(50)  NOT NULL REFERENCES questions (question_id),
    category        VARCHAR(100) NOT NULL,
    question_type   VARCHAR(30)  NOT NULL DEFAULT '',
    question_text   TEXT         NOT NULL,
    status          VARCHAR(30)  NOT NULL,          -- 'Passed' | 'Failed' | 'Not Enough Info'
    actual_response TEXT         NOT NULL DEFAULT '',
    comment         TEXT         NOT NULL DEFAULT '',
    submitted_at    TIMESTAMPTZ  NOT NULL,
    CONSTRAINT uq_tester_question UNIQUE (tester_key, question_id)
);
CREATE INDEX IF NOT EXISTS ix_evaluations_tester_key ON evaluations (tester_key);
CREATE INDEX IF NOT EXISTS ix_evaluations_department ON evaluations (department);
