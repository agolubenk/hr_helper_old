(function($) {
    'use strict';
    
    function toggleGradeField() {
        var rejectionType = $('#id_rejection_type').val();
        var gradeField = $('.form-row.field-grade');
        
        if (rejectionType === 'grade') {
            gradeField.show();
            $('#id_grade').prop('required', true);
        } else {
            gradeField.hide();
            $('#id_grade').val('').prop('required', false);
        }
    }
    
    $(document).ready(function() {
        // Инициализация при загрузке страницы
        toggleGradeField();
        
        // Обработка изменения типа отказа
        $('#id_rejection_type').on('change', toggleGradeField);
    });
})(django.jQuery);


