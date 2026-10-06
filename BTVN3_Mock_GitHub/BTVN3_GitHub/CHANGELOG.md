# Thay đổi khi tổ chức lại dự án

## Bản chỉ dùng model giả

- Khôi phục phần đầu bị thiếu của file gửi lên: imports, hàm JSON và khai báo Constraints.
  Bản gửi bắt đầu ở `ck_time(12, 0)`, không phải đầu file Python hợp lệ.
- Chuẩn hóa khoảng trắng không ngắt dòng thành khoảng trắng Python thông thường.
- Tách cấu hình, tool, harness, model giả, kế hoạch, graph, runner, đánh giá và CLI thành module.
- Thêm ba file chạy riêng cho ReAct, Plan và Lai; giữ điểm vào tổng hợp cũ.
- Giữ nguyên năm kịch bản, tiêu chí chấm và giới hạn thời gian 120 giây của file gửi lên.
- Loại đường chạy LLM thật, bộ chuyển JSON của UIT, adapter OpenAI và cấu hình kết nối.
- Thêm README, bộ kiểm thử unittest, requirements và .gitignore.
- So sánh với file gốc sau khôi phục: 15/15 ca có cùng trạng thái dừng, booking,
  số lượt model/tool, replan, kết quả chấm và vi phạm. Không so thời gian thực thi.

Không có API key, môi trường ảo, cache hoặc kết quả LLM thật trong gói phát hành.

- Đối chiếu trực tiếp với mã đầy đủ trong ZIP gốc: 15/15 ca mock giữ nguyên kết quả và số lần gọi model/tool.
