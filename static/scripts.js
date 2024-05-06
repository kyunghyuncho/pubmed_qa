$(document).ready(function() {
    $('#search-form').on('submit', function(e) {
        e.preventDefault();
        const question = $('#question').val();
        const search_terms = $('#search_terms').val();
        // Show the spinner and clear the output areas
        $('.spinner-container').show();
        $('#abstracts').html('');
        $('#summary_box').val('');

        $.ajax({
            url: '/get_abstracts',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ question: question , search_terms: search_terms }),
            success: function(response) {
                $('.spinner-container').hide();
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
                $('.spinner-container').hide();
                $('#abstracts').text('Error: Unable to fetch abstracts.');
                $('#summary_box').val('');
            }
        });
    });

    $('#extract-terms').on('click', function() {
        const question = $('#question').val();
        if (question) {
            $.ajax({
                url: '/extract_terms',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ question: question }),
                success: function(response) {
                    // Ensure the response contains the 'terms' field before updating the search terms textbox
                    if ('terms' in response) {
                        $('#search_terms').val(response.terms.join(' '));
                    } else {
                        $('#search_terms').val('No terms extracted.');
                    }
                },
                error: function(xhr) {
                    $('#search_terms').val('Error: Unable to extract search terms.');
                }
            });
        } else {
            $('#search_terms').val('No question provided.');
        }
    });
});
