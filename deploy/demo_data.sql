INSERT INTO `student_profile`
(`id`, `student_id`, `class_name`, `major`, `grade`, `moral_score`, `academic_score`)
VALUES
(1, '202311080001', '2023级1班', '计算机科学与技术', '2023', 82.0, 86.5),
(2, '202311080002', '2023级1班', '计算机科学与技术', '2023', 85.0, 91.0),
(3, '202311080003', '2023级1班', '软件工程', '2023', 80.0, 88.0);

INSERT INTO `score_result`
(`student_id`, `moral_score`, `academic_score`, `innovation_score`, `work_score`, `total_score`)
VALUES
((SELECT id FROM `student_profile` WHERE `student_id` = '202311080001'), 82.0, 86.5, 0.0, 0.0, 168.5),
((SELECT id FROM `student_profile` WHERE `student_id` = '202311080002'), 85.0, 91.0, 0.0, 0.0, 176.0),
((SELECT id FROM `student_profile` WHERE `student_id` = '202311080003'), 80.0, 88.0, 0.0, 0.0, 168.0);
