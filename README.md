# SE373 — BTVN #3: Agent đặt vé máy bay (model giả)

File chạy nằm ở thư mục gốc, thành phần tái sử dụng nằm trong `lib/`.

| File | Trách nhiệm |
|---|---|
| `agent_react.py` | Chạy riêng ReAct |
| `agent_plan_execute.py` | Chạy riêng Plan-then-Execute |
| `agent_lai.py` | Chạy riêng mẫu Lai |
| `danh_gia.py` | Chạy đánh giá cả ba mẫu |
| `btvn3_agent_dat_ve.py` | Điểm chạy tổng hợp|
| `lib/config.py` | Constraints, PermissionPolicy, Limits, tên kịch bản |
| `lib/tools_dat_ve.py` | Dữ liệu chuyến, backend MockAirline và năm tool |
| `lib/harness.py` | Kiểm quyền, ràng buộc, hoàn thành, dừng và bàn giao |
| `lib/model_gia.py` | ModelGia kế thừa BaseChatModel |
| `lib/planning.py` | Schema Plan, chọn phương án và điền tham số |
| `lib/agents.py` | Graph ReAct, Plan và Lai; system prompt |
| `lib/runner.py` | Tạo một phiên mới và chấm từ backend |
| `lib/evaluation.py` | Tổng hợp kết quả, xuất CSV/JSON |
| `lib/checks.py` | Các kiểm thử nghiệp vụ và harness |
| `lib/cli.py` | Tham số dòng lệnh dùng chung |
| `lib/utils.py` | Hàm JSON dùng chung |
| `tests/test_harness.py` | Chạy bộ kiểm thử bằng unittest |
| `requirements.txt` | Thư viện trực tiếp cần cài |
| `requirements-lock.txt` | Phiên bản thư viện trực tiếp đã dùng kiểm thử |
| `.gitignore` | Bỏ qua môi trường ảo, cache, file bí mật và kết quả sinh ra |
| `CHANGELOG.md` | Các thay đổi khi chia lại file |

`lib/__init__.py` đánh dấu package. Các file chạy chỉ gọi CLI chung, không sao chép
logic agent. Chạy lệnh tại thư mục chứa README này, không chạy riêng `lib/*.py`.

## Cài đặt trên Windows / PowerShell

Python 3.10 trở lên. Mở thư mục dự án bằng VS Code, chọn Terminal → New Terminal.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu muốn cố định các thư viện trực tiếp ở phiên bản đã được kiểm thử (các phụ thuộc gián tiếp vẫn do pip giải quyết):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Nếu máy đã có `.venv` từ bài trước, có thể dùng lại môi trường đó khi đã đủ thư viện;
không cần cài adapter OpenAI hay nhập key.

macOS/Linux: tạo môi trường bằng `python3 -m venv .venv`, sau đó dùng
`.venv/bin/python` thay cho `.\.venv\Scripts\python.exe` trong các lệnh dưới.

## Chạy từng mẫu

```powershell
.\.venv\Scripts\python.exe agent_react.py --scenario normal
.\.venv\Scripts\python.exe agent_plan_execute.py --scenario normal
.\.venv\Scripts\python.exe agent_lai.py --scenario normal
```

So sánh khi chuyến đầu hết chỗ:

```powershell
.\.venv\Scripts\python.exe agent_react.py --scenario sold_out
.\.venv\Scripts\python.exe agent_plan_execute.py --scenario sold_out
.\.venv\Scripts\python.exe agent_lai.py --scenario sold_out
```

Cách gọi tổng hợp cũ vẫn được hỗ trợ:

```powershell
.\.venv\Scripts\python.exe btvn3_agent_dat_ve.py --architecture react --scenario normal
```

Model mặc định luôn là `mock`; `--model mock` chỉ giữ để tương thích lệnh cũ.
Các giá trị model khác bị từ chối. Không cần sửa source để chọn kiến trúc.

## Đánh giá và kiểm thử

```powershell
.\.venv\Scripts\python.exe btvn3_agent_dat_ve.py --self-test
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe danh_gia.py --out results_mock
```

Hai lệnh kiểm thử trên chạy cùng bộ kiểm tra qua hai điểm vào khác nhau, chọn một là đủ.
Lệnh đánh giá chạy 3 mẫu × 5 kịch bản = 15 lượt. Kết quả lưu trong:

- `results_mock/evaluation.csv`: số liệu từng lượt; mở bằng Excel.
- `results_mock/summary.json`: số liệu tổng hợp.
- Các JSON còn lại: trạng thái booking, bàn giao và trace của mỗi lần chạy.

Có thể thêm `--repeats 3`, nhưng model giả xác định nên lặp lại chủ yếu phục vụ kiểm tra
độ ổn định chương trình; không biến kết quả thành đánh giá năng lực LLM thật.

## Năm kịch bản

| Kịch bản | Tình huống |
|---|---|
| `normal` | Có chuyến hợp lệ và đủ quyền đặt/thanh toán |
| `sold_out` | VN122 hết chỗ khi kiểm ghế; còn VN134 thay thế |
| `over_budget` | Giá mỗi chuyến tăng thêm 2 triệu ngay trong dữ liệu tìm kiếm |
| `need_approval` | Được giữ ghế nhưng chưa được thanh toán |
| `timeout` | Tool tìm chuyến liên tục timeout |

## Bốn chức năng harness

1. **Ràng buộc là dữ liệu:** `Constraints` trong config.py; `is_ok()` kiểm tuyến,
   ngày, trước 12:00, giá không quá 2 triệu VND.
2. **Hoàn thành bằng code:** `BookingHarness.is_done()` cần booking đã đọc lại,
   confirmed, paid, đúng hành khách và ràng buộc.
3. **Kiểm quyền:** `PermissionPolicy` và `guard()` trước tool có tác dụng phụ.
4. **Bàn giao:** `finish()` trả lý do, lịch sử, trạng thái và câu hỏi cho người.

Bổ sung kiểm schema, vòng lặp, tiến triển, ngân sách và chống giữ ghế/thanh toán trùng.
Chính sách quyền do fixture cấp, model không có quyền tự thay đổi.

## Ba mẫu thiết kế trong code

- **ReAct:** ModelGia chọn tool từ observation sau mỗi bước.
- **Plan-then-Execute:** ModelGia sinh kế hoạch một lần; executor điền tham số bằng code.
  Khi một bước lỗi, dừng và bàn giao.
- **Lai:** chạy kế hoạch, review sau tối đa hai bước hoặc ngay khi lỗi;
  lập lại kế hoạch khi observation cho thấy lỗi.

LangChain cung cấp BaseChatModel, message và `@tool`. LangGraph tổ chức StateGraph.
Không gọi `create_agent()` vì vòng điều khiển và vị trí harness được thể hiện trực tiếp.

## Kết quả mock sau khi tách module

| Chỉ số | ReAct | Plan | Lai |
|---|---:|---:|---:|
| Đúng kỳ vọng | 5/5 | 4/5 | 5/5 |
| Đặt thành công trên ca khả thi | 2/2 | 1/2 | 2/2 |
| Lượt model trung bình | 4,0 | 1,0 | 1,6 |
| Lượt tool trung bình | 3,6 | 2,4 | 3,6 |
| Booking vi phạm ràng buộc | 0 | 0 | 0 |
| Thanh toán chưa có quyền | 0 | 0 | 0 |
