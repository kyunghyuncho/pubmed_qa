$(document).ready(function() {
    $('#search-form').on('submit', function(e) {
        e.preventDefault();
        const question = $('#question').val();

        $.ajax({
            url: '/get_abstracts',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ question: question }),
            success: function(response) {
                if ('articles' in response) {
                    let abstractsContent = "";

                    response.articles.forEach(article => {
                        abstractsContent += `
                            <h5>${article.title}</h5>
                            <p><strong>Authors:</strong> ${article.authors}</p>
                            <p><strong>Year:</strong> ${article.year}</p>
                            <p><strong>Abstract:</strong> ${article.abstract}</p>
                            <hr>
                        `;
                    });

                    $('#abstracts').html(abstractsContent);
                    $('#summary_box').val(response.summary);
                } else {
                    $('#abstracts').text('No articles found.');
                    $('#summary_box').val('');
                }
            },
            error: function(xhr) {
                $('#abstracts').text('Error: Unable to fetch abstracts.');
                $('#summary_box').val('');
            }
        });
    });
});
