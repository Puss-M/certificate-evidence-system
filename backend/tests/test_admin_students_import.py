"""
学生Excel导入接口测试（POST /api/admin/students/import）。

覆盖：正常导入多行、缺表头必填列时报400、单行学号/姓名为空记为失败但不影响
其他行、学号和数据库里已有学生重复记为失败、导入完成后会顺带建一个批次记录。
"""
import asyncio
import io

import httpx
from openpyxl import Workbook

from app.main import app
from app.models.certificate_batch import CertificateBatch
from app.models.student import Student


def _build_excel(rows: list[tuple], header: tuple = ("学号", "姓名", "学院", "班级", "专业")) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


async def _post_import(content: bytes, batch_name: str = "测试批次", template_id: int = 1) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(
            "/api/admin/students/import",
            data={"batch_name": batch_name, "template_id": str(template_id)},
            files={"file": ("students.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )


def test_import_students_success(db_session) -> None:
    content = _build_excel(
        [
            ("2023101", "张三", "计算机学院", "1班", "软件工程"),
            ("2023102", "李四", "计算机学院", "1班", "软件工程"),
        ]
    )

    response = asyncio.run(_post_import(content))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success_count"] == 2
    assert data["failed_count"] == 0

    saved = db_session.query(Student).filter(Student.student_no.in_(["2023101", "2023102"])).all()
    assert len(saved) == 2
    assert {student.college for student in saved} == {"计算机学院"}

    # 导入之后应该顺带建了一个批次记录
    batches = db_session.query(CertificateBatch).all()
    assert len(batches) == 1
    assert batches[0].batch_name == "测试批次"


def test_import_students_reports_row_level_failures(db_session) -> None:
    existing = Student(student_no="2023200", student_name="王五")
    db_session.add(existing)
    db_session.commit()

    content = _build_excel(
        [
            ("2023201", "赵六", "", "", ""),
            ("", "缺学号", "", "", ""),
            ("2023202", "", "", "", ""),
            ("2023200", "重复的学号", "", "", ""),  # 和数据库里已有的学生重复
        ]
    )

    response = asyncio.run(_post_import(content))

    data = response.json()["data"]
    assert data["success_count"] == 1
    assert data["failed_count"] == 3
    reasons = [f["reason"] for f in data["failures"]]
    assert any("学号为空" in r for r in reasons)
    assert any("姓名为空" in r for r in reasons)
    assert any("学号重复" in r for r in reasons)


def test_import_students_rejects_missing_required_headers(db_session) -> None:
    content = _build_excel([("张三", "1班")], header=("姓名", "班级"))

    response = asyncio.run(_post_import(content))

    assert response.status_code == 400


def test_import_students_supports_english_headers(db_session) -> None:
    content = _build_excel(
        [("2023301", "孙七", "计算机学院", "2班", "计算机")],
        header=("student_no", "student_name", "college", "class_name", "major_name"),
    )

    response = asyncio.run(_post_import(content))

    data = response.json()["data"]
    assert data["success_count"] == 1
    assert db_session.query(Student).filter_by(student_no="2023301").one().college == "计算机学院"


def test_import_students_rejects_overlong_college_without_saving_student(db_session) -> None:
    content = _build_excel(
        [("2023401", "超长学院测试", "学" * 101, "3班", "软件工程")]
    )

    response = asyncio.run(_post_import(content))
    data = response.json()["data"]

    assert data["success_count"] == 0
    assert data["failed_count"] == 1
    assert data["failures"][0]["reason"] == "学院名称不能超过100个字符"
    assert db_session.query(Student).filter_by(student_no="2023401").one_or_none() is None
