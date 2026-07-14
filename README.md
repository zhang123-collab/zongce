# 本科生综测自动算分系统（基础业务版）

当前版本以成员 B 的基础业务改进版为主干，整合了成员 E 的审核端和管理端界面。系统包含三角色登录、学生资料、学生单个新增与 Excel 批量导入、加分申请、证明材料、教师审核、班级与规则管理。后端使用 FastAPI + SQLAlchemy + SQLite，前端资源已从 Python 入口中分离。

当前主线继续使用无需构建即可运行的原生前端，但已吸收新增Vue学生端和审核/管理端中较成熟的视觉设计：统一深色角色侧栏、顶部阶段状态栏、真实数据工作台、卡片式统计、响应式布局和学生规则分数预估。新增Vue目录中的Mock账号、固定业务数据、旧后端和数据库未合入，所有主线页面仍直接使用当前FastAPI接口。

## 目录结构

```text
app.py                         应用入口、路由组合、静态资源和异常处理
static/index.html              前端页面骨架
static/app.css                 三角色页面样式
static/common.js               请求、登录、材料访问、转义和弹窗
static/student.js              学生信息与申请交互
static/teacher.js              教师班级管理与审核交互
static/admin.js                班级、规则和账号管理交互
static/app.js                  按角色启动页面
zongce/core.py                 配置、数据库模型、JWT认证和公共权限
zongce/seed.py                 演示账号、材料和规则初始化
zongce/application_service.py  申请状态机、分页和字段校验
zongce/accounting_service.py   成绩聚合、分类封顶、扣分和终审核算
zongce/batch_service.py        批量申报Excel解析、规则匹配和安全文件校验
zongce/ai/redaction.py         发送模型前的身份、联系方式、路径和文件名脱敏
zongce/ai/extraction.py        PDF文本提取及可选的本地图片/扫描件OCR
zongce/ai/deepseek.py          DeepSeek结构化调用与本机配置读取
zongce/ai/task_service.py      AI后台任务、响应校验和建议落库
zongce/routers/members.py      登录、个人资料、学生管理和Excel导入
zongce/routers/applications.py 申请、材料上传和材料鉴权
zongce/routers/audits.py       教师审核、审核列表和审核记录
zongce/routers/rules.py        规则查询与管理员规则维护
zongce/routers/admin.py        教师、班级、用户和管理员账号管理
zongce/routers/accounting.py   核算明细、扣分、终审、统计和Excel导出
zongce/routers/batches.py      学生批次上传、预览确认、模板和材料访问
zongce/routers/ai.py           AI配置状态、批次分析和结果权限接口
zongce/routers/publications.py 公示与异议流程
zongce/routers/reports.py      个人PDF报告接口
zongce/report_service.py       跨平台PDF报告生成
scripts/check_environment.py   启动前依赖、目录、数据库和端口检查
scripts/backup_data.py         SQLite与上传材料一致性备份
tests/                         静态契约与业务回归测试
```

## 本地启动

需要交给助教或在新电脑部署时，请优先阅读 `项目说明.md`。项目已提供 `Dockerfile` 与 `docker-compose.yml`，可使用 `docker compose up --build -d` 在本地容器化启动；Docker 演示数据不包含真实学生材料。

Windows下推荐直接依次双击：

1. `安装依赖.bat`
2. `启动系统.bat`

`启动系统.bat` 会先检查Python依赖、上传目录、SQLite完整性、DeepSeek配置和8000端口。若未显式配置 `ZONGCE_SECRET_KEY`，首次启动会生成仅保存在本机、已被 `.gitignore` 排除的 `.zongce_secret`，后续启动继续复用。

需要备份时双击 `备份数据.bat`，系统会使用SQLite在线备份机制，将一致性数据库快照和 `uploads` 打包到 `backups`。备份中可能包含个人信息，不可上传到公开仓库。

也可以在 PowerShell 中进入本目录后手动执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

如需识别 JPG、PNG 或扫描版 PDF，再安装本地 OCR 可选依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
```

如果 Python 在中文路径下创建虚拟环境失败，可把整个 `项目(1)` 目录复制到纯英文路径后执行以上命令，或使用已有虚拟环境安装 `requirements.txt`。

浏览器访问 `http://127.0.0.1:8000`，接口文档位于 `http://127.0.0.1:8000/docs`。

首次启动时会在本目录生成 `zongce.db`。若存在 `data.sql`，程序会优先读取其中的学生、规则和成绩；若不存在，则根据 `学生证明材料` 中符合命名规范的 PDF 创建演示学生。默认演示密码均为 `123456`：

- 管理员：`admin`
- 教师：`teacher01`
- 学生：账号为材料文件名中的学号

演示完成后应立即修改默认密码。不要将 `.env`、`zongce.db`、`uploads` 或包含个人信息的证明材料提交到公开仓库。

## 业务约束

- 新申请先保存为草稿，上传至少一份材料后才能提交。
- 草稿、未通过和已撤回申请可以修改；修改后恢复为草稿并可重新提交。
- 每个申请最多上传 5 份 JPG、PNG 或 PDF，单文件不超过 10 MB；服务端会校验文件内容特征，并使用随机磁盘文件名保存。
- 学生只能访问自己的申请和材料。
- 教师只能查看、审核和修改自己负责班级的数据；负责班级只能由管理员设置。
- 管理员可以跨班级管理和审核。
- 连续5次登录失败会锁定账号30分钟，管理员可通过用户编辑接口解锁。
- 删除存在历史申请的学生时只停用账号，不破坏业务记录。
- 教师和管理员存在历史审核记录时不物理删除，只停用账号以保留审计链。
- 审核意见最多500字，人工修改后的单项分数范围为0-100。
- 前端动态文本统一使用HTML转义，材料只能通过鉴权接口打开。
- 请求参数校验错误使用统一的 `code/message/data` 响应结构；数据库请求异常时会自动回滚事务。
- 审核通过的申请按规则聚合后计入学术创新和学生工作，两项分别封顶7分；学生工作中的岗位任职封顶3分、其余活动合计封顶4分。
- 扣分采用软删除并保留操作日志；管理员终审后，基础分、申请、材料、审核和扣分全部锁定，撤销终审必须填写原因。
- 学生可查看个人核算明细，负责班级教师可查看班级结果，管理员可统计并导出包含汇总、加分和扣分明细的Excel。
- 学生可使用标准模板一次上传一份Excel和最多5份证明材料；系统逐行校验身份、字段、日期、申报分和规则匹配，确认后才生成现有草稿申请。
- XLSX会检查ZIP内部结构、解压大小和路径安全；PDF/JPG/PNG会校验真实文件头，批次文件使用随机磁盘名保存。

## 核算系统整合说明

本版本吸收了独立核算 Demo 中确定性的成绩汇总、扣分、终审、操作追溯和 Excel 导出能力，并继续使用现有 FastAPI、JWT、SQLAlchemy 与三角色权限体系。班长职责映射为现有“负责班级教师”，管理员老师映射为管理员。

独立 Demo 的标准库 HTTP 服务、明文密码、内存会话和单文件页面没有合入。当前已接入独立的材料本地提取/可选OCR、脱敏和 DeepSeek 辅助核验模块；自然语言细则 PDF 导入和个人 PDF 报告仍未接入。AI输出只作为人工复核建议，不能直接修改规则分、申请状态或最终成绩。

## 材料脱敏与 DeepSeek 辅助核验

复制 `.env.example` 为本机 `.env`，配置已经轮换的新密钥：

```dotenv
DEEPSEEK_API_KEY=在此填写新密钥
DEEPSEEK_API_URL=https://api.deepseek.com/chat/completions
DEEPSEEK_MODEL=deepseek-chat
ZONGCE_AI_ENABLED=1
```

`.env` 已加入 `.gitignore`。不要把真实密钥写入源码、测试、启动脚本、截图或群聊；密钥一旦公开应立即在 DeepSeek 控制台作废并重新生成。

学生上传并成功解析批次后，可点击“材料脱敏并由AI辅助核验”。处理顺序为：本机提取 PDF 文本或执行可选 OCR → 删除姓名、学号、手机号、邮箱、长数字、本地路径和原文件名 → 截取与项目相关的短片段 → 调用 DeepSeek → 校验结构化响应并保存建议。原始提取文本不写入数据库，DeepSeek错误响应正文和密钥也不会写入日志。

未安装 OCR 时，文本型 PDF 仍可分析，图片和扫描版 PDF 会明确标记为需要人工核验；未配置密钥、服务不可用或模型返回异常时，批次申报、规则计分、人工审核和终审核算均可继续使用。

## Excel批量申报

学生端“Excel批量申报”提供带登录鉴权的模板下载。模板必须包含“学生汇总”和“申报明细”工作表；姓名、学号必须与当前账号一致。解析成功的批次需要学生再次确认，确认后每一行生成一条草稿申请，并复用原有材料鉴权、提交、教师审核、核算和终审流程。

批次限制：Excel不超过5MB，最多100条明细；证明材料最多5份、单份不超过10MB、总计不超过30MB。解析错误会精确返回Excel行号，错误批次不会生成申请。

## 学生 Excel 导入

管理员页面“班级与师生管理”提供 Excel 导入入口。文件必须为 `.xlsx`，单次最多1000行、5MB。必需列为：

```text
学号、姓名、班级、专业、年级、思品分、学业成绩
```

可选列为：`登录账号、初始密码、邮箱、电话`。接口会返回成功数量以及失败行和原因。

## 公示、排名、材料复核与个人报告

- 核算接口基于同一份实时结果生成班级排名和年级排名；管理员可手动重算并保存排名，Excel汇总也包含两类排名。
- 管理员可按全部学生、班级、专业或年级发布成绩公示并设置起止时间；学生只能看到与自己相关的公示和本人公示成绩。
- 学生仅能在有效公示期内提交异议，同一公示、同一分数项不能重复提交待处理异议。异议成立不会绕过审核直接改分，管理员需撤销终审后按原核算流程修正。
- 新上传材料会计算SHA-256摘要；教师仅能查看负责班级、管理员可查看全校的完全重复材料分组。旧材料在启动时自动补算摘要。
- 普通单条申请和Excel批量申请都支持“本地提取/OCR → 脱敏 → DeepSeek辅助核验”，AI结果始终只作建议。
- 学生、负责教师和管理员可按原有权限导出个人综合测评PDF报告。

PDF报告依赖已经写入 `requirements.txt`。更新已有环境时执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 回归检查

```powershell
python -m unittest discover -s tests -v
```

当前检查覆盖模块语法、路由注册、登录锁定、Excel导入、材料鉴权、教师审核范围、驳回重提、批次申报、排名、公示异议、重复材料、个人PDF、单条/批量材料脱敏、AI建议权限及“AI不得改分”等关键边界。
