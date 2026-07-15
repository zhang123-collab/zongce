/* =============== 启动渲染 =============== */
function render(){
  renderHeader();
  if(!currentUser){ renderLogin(); return; }
  if(currentUser.role === 0) renderStudent();
  else if(currentUser.role === 1) renderTeacher();
  else renderAdmin();
}
render();
